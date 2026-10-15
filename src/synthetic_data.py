"""Reproducible fleet simulation, calibrated on historical aggregates. Not future forecasts."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd
from src.model_benchmark import TARGETS, load_daily, supply, write_json

START = '2026-01-01'
END = '2035-12-31'
PATHS = [('baseline', 42), ('baseline', 123), ('baseline', 2026), ('demand_shift', 42), ('maintenance_stress', 42)]


def calendar(index):
    phase=2*np.pi*(index.dayofyear.to_numpy()-1)/365.25
    return np.column_stack([np.ones(len(index)),*[np.asarray(index.dayofweek==i,float) for i in range(1,7)],
                            np.sin(phase),np.cos(phase),np.sin(2*phase),np.cos(2*phase)])


def fit_daily(daily):
    x=calendar(daily.index);y=daily[TARGETS].to_numpy(float)
    penalty=np.eye(x.shape[1])*5;penalty[0,0]=0
    coefficients=np.linalg.solve(x.T@x+penalty,x.T@y)
    residuals=y-x@coefficients
    return coefficients,residuals


def simulate_daily(source, dates, seed, scenario='baseline', block_days=28):
    if scenario not in {'baseline','demand_shift','maintenance_stress'}:raise ValueError('Unknown scenario')
    rng=np.random.default_rng(seed);coef,res=fit_daily(source)
    donors=[]
    for start in range(0,len(dates),block_days):
        # Joint blocks preserve within-block lag structure and cross-component dependence.
        candidates=np.flatnonzero(source.index.dayofweek==dates[start].dayofweek)
        begin=int(rng.choice(candidates));donors.extend((begin+np.arange(block_days))%len(source))
    donors=np.asarray(donors[:len(dates)])
    jitter=rng.normal(size=(len(dates),len(TARGETS)))*np.std(res,axis=0)*.025
    values=calendar(dates)@coef+res[donors]+jitter
    out=pd.DataFrame(values,index=dates,columns=TARGETS)
    out['num_tails']=source.num_tails.to_numpy()[donors].astype(int)
    events=[]
    if scenario=='demand_shift':
        ramp=np.clip((dates-pd.Timestamp('2033-01-01')).days.to_numpy()/180,0,1)
        out['daily_quote_count']*=1+.25*ramp
        events.append({'start':'2033-01-01','end':'2035-12-31','change':'Enquiries ramp to +25% over 180 days; other components unchanged by intervention'})
    if scenario=='maintenance_stress':
        for year in [2033,2034,2035]:
            start=pd.Timestamp(f'{year}-06-01');end=start+pd.Timedelta(days=59)
            mask=(dates>=start)&(dates<=end)
            out.loc[mask,'smx_rate']+=.08;out.loc[mask,'umx_rate']+=.04
            events.append({'start':str(start.date()),'end':str(end.date()),'change':'SMX +8pp, UMX +4pp; planned synthetic shock'})
    out[TARGETS[:4]]=out[TARGETS[:4]].clip(0,1)
    totals=out[TARGETS[:4]].sum(axis=1)
    # Existing arithmetic treats these as additive unavailable fractions.
    over=totals>1
    out.loc[over,TARGETS[:4]]=out.loc[over,TARGETS[:4]].div(totals[over],axis=0)
    out[TARGETS[4:]]=np.rint(out[TARGETS[4:]].clip(lower=0)).astype(int)
    out.index.name='date'
    return out,events


def quote_distribution(quotes):
    q=quotes.copy()
    lead=(pd.to_datetime(q.dep_date)-pd.to_datetime(q.quote_date)).dt.days
    data=pd.DataFrame({'month':pd.to_datetime(q.quote_date).dt.month,
        'quoted_bin':np.floor(q.yield_per_eft/500).fillna(-1).astype(int),
        'final_bin':np.floor(q.final_yield/500).fillna(-1).astype(int),
        'booked':q.booked.astype(int),'lead_bin':np.floor(lead.clip(0,420)/7).astype(int)})
    return data.groupby(list(data.columns)).size().rename('n').reset_index()


def simulate_quotes(daily, distribution, seed, scenario):
    rng=np.random.default_rng(seed+10000)
    dates=np.repeat(daily.index.to_numpy(),daily.daily_quote_count.to_numpy(int))
    q=pd.DataFrame({'quote_date':pd.to_datetime(dates)})
    for col in ['yield_per_eft','final_yield']:q[col]=np.nan
    q['booked']=0;q['dep_date']=q.quote_date
    for month in range(1,13):
        idx=np.flatnonzero(q.quote_date.dt.month.to_numpy()==month);pool=distribution[distribution.month==month]
        if pool.empty:pool=distribution
        selected=pool.iloc[rng.choice(len(pool),len(idx),p=pool.n/pool.n.sum())]
        for col,bucket in [('yield_per_eft','quoted_bin'),('final_yield','final_bin')]:
            bins=selected[bucket].to_numpy();q.loc[idx,col]=np.where(bins<0,np.nan,(bins+rng.uniform(0,1,len(idx)))*500)
        q.loc[idx,'booked']=selected.booked.to_numpy()
        leads=selected.lead_bin.to_numpy()*7+rng.integers(0,7,len(idx))
        q.loc[idx,'dep_date']=q.loc[idx,'quote_date']+pd.to_timedelta(leads,unit='D')
    q['is_synthetic']=True;q['scenario']=scenario;q['seed']=seed
    return q


def diagnostics(real, generated, real_quotes, generated_quotes):
    rows=[]
    for c in TARGETS:
        a=real[c];b=generated[c]
        rows.append({'component':c,'real_mean':float(a.mean()),'synthetic_mean':float(b.mean()),
            'mean_shift_in_real_std':float((b.mean()-a.mean())/a.std()) if a.std() else None,
            'real_std':float(a.std()),'synthetic_std':float(b.std()),
            'real_p05':float(a.quantile(.05)),'synthetic_p05':float(b.quantile(.05)),
            'real_p95':float(a.quantile(.95)),'synthetic_p95':float(b.quantile(.95)),
            'real_lag1':float(a.autocorr(1)),'synthetic_lag1':float(b.autocorr(1)),
            'real_lag7':float(a.autocorr(7)),'synthetic_lag7':float(b.autocorr(7)),
            'weekday_profile_mae':float(abs(a.groupby(a.index.dayofweek).mean()-b.groupby(b.index.dayofweek).mean()).mean()),
            'monthly_profile_mae':float(abs(a.groupby(a.index.month).mean()-b.groupby(b.index.month).mean()).mean())})
    corrdiff=abs(real[TARGETS].corr()-generated[TARGETS].corr()).to_numpy()
    def qstats(q):return {'rows':len(q),'booking_rate':float(q.booked.mean()),
        'quoted_yield_missing_fraction':float(q.yield_per_eft.isna().mean()),'final_yield_missing_fraction':float(q.final_yield.isna().mean()),
        'median_quoted_yield':float(q.yield_per_eft.median()),'median_lead_days':float((pd.to_datetime(q.dep_date)-pd.to_datetime(q.quote_date)).dt.days.median())}
    return {'daily':rows,'mean_absolute_correlation_difference':float(corrdiff[np.triu_indices(len(TARGETS),1)].mean()),
            'real_zero_supply_fraction':float((supply(real,real.num_tails)<=0).mean()),
            'synthetic_zero_supply_fraction':float((supply(generated,generated.num_tails)<=0).mean()),
            'real_quotes':qstats(real_quotes),'synthetic_quotes':qstats(generated_quotes)}


def save_path(daily,quotes,out,scenario,seed):
    processed=out/'data/processed';processed.mkdir(parents=True)
    groups=[('avl_fleet_daily','DATE_DAY',TARGETS[:4]+['num_tails']),('legs_fleet_daily','dep_date',TARGETS[4:6]),('quotes_fleet_daily','quote_date',TARGETS[6:])]
    for name,date,cols in groups:
        d=daily[cols].reset_index().rename(columns={'date':date});d['is_synthetic']=True;d['scenario']=scenario;d['seed']=seed
        d.to_parquet(processed/f'{name}.parquet',index=False)
    quotes.to_parquet(processed/'quotes_deduped_enriched.parquet',index=False)
    d=daily.reset_index();d['is_synthetic']=True;d['scenario']=scenario;d['seed']=seed
    d.to_csv(out/'synthetic_daily.csv',index=False)


def evaluation_plan():
    # Nonoverlapping quarters for each horizon. All dates below are simulation time.
    folds=[]
    for split,years in [('validation',[2032]),('test',[2033,2034,2035])]:
        for year in years:
            for month in [1,4,7,10]:
                start=pd.Timestamp(year,month,1);origin=start-pd.Timedelta(days=1)
                for horizon in [14,28,90]:
                    folds.append({'split':split,'train_start':START,'origin':str(origin.date()),'horizon':horizon,
                                  'forecast_start':str(start.date()),'forecast_end':str((start+pd.Timedelta(days=horizon-1)).date())})
    return folds


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():p.error('Choose a new output directory')
    daily=load_daily(args.root);quotes=pd.read_parquet(args.root/'data/processed/quotes_deduped_enriched.parquet')
    for c in ['quote_date','dep_date']:quotes[c]=pd.to_datetime(quotes[c])
    args.out.mkdir(parents=True)
    distribution=quote_distribution(quotes);dates=pd.date_range(START,END)
    inventory=[]
    for scenario,seed in PATHS:
        name=f'{scenario}_seed{seed}';out=args.out/name
        generated,events=simulate_daily(daily,dates,seed,scenario)
        gq=simulate_quotes(generated,distribution,seed,scenario)
        save_path(generated,gq,out,scenario,seed)
        write_json(out/'quality.json',diagnostics(daily,generated,quotes,gq));write_json(out/'events.json',events)
        inventory.append({'path':name,'scenario':scenario,'seed':seed,'start':START,'end':END,'days':len(generated),'enquiries':len(gq)})
        print(f'{name}: {len(generated)} days, {len(gq)} enquiries',flush=True)
    manifest={'is_synthetic':True,'version':'fleet-simulation-v1','calibration_start':str(daily.index.min().date()),'calibration_end':str(daily.index.max().date()),
              'original_days':len(daily),'original_enquiries':len(quotes),'paths':inventory,
              'source_hashes':{f.name:sha256(f.read_bytes()).hexdigest() for f in (args.root/'data/processed').glob('*.parquet') if f.stem in ['avl_fleet_daily','legs_fleet_daily','quotes_fleet_daily','quotes_deduped_enriched']},
              'code_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
              'warning':'Simulation labels are not forecasts or recovered history. Calibrated on all real 2024–2025 data; NOT eligible for augmentation evaluated on that same real period.',
              'method':'Calendar regression + joint 28-day residual block resampling + 2.5% residual-SD jitter; monthly joint quote/booking/lead histograms.'}
    write_json(args.out/'manifest.json',manifest)
    pd.DataFrame(evaluation_plan()).to_csv(args.out/'evaluation_plan.csv',index=False)
    write_json(args.out/'source_quality.json',{'negative_lead_rows':int(((quotes.dep_date-quotes.quote_date).dt.days<0).sum()),
            'quote_date_daily_count_matches':bool(quotes.groupby('quote_date').size().reindex(daily.index,fill_value=0).equals(daily.daily_quote_count.astype('int64')))})

if __name__=='__main__':main()
