"""Offline rolling-origin benchmark; LLM calls require explicit --allow-paid.
Never overwrites operational forecasts. Run python -m src.model_benchmark --help.
"""
import argparse
from datetime import timedelta
from hashlib import sha256
import json
import math
from pathlib import Path
import time

import numpy as np
import pandas as pd
from pydantic import BaseModel

TARGETS = ['aog_rate', 'smx_rate', 'umx_rate', 'cna_rate',
           'program_live_legs', 'non_program_live_legs', 'daily_quote_count']
GRID = list(range(7000, 15001, 500))
VERSION = 'dpe-benchmark-v1'


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False, default=str))


def metrics(actual, predicted):
    a, p = np.asarray(actual, float), np.asarray(predicted, float)
    if len(a) == 0 or a.shape != p.shape or not np.isfinite(a).all() or not np.isfinite(p).all():
        raise ValueError('Metrics require aligned finite nonempty arrays')
    e = p-a
    return {'n':len(a), 'mae':float(np.mean(abs(e))), 'rmse':float(np.sqrt(np.mean(e**2))),
            'bias':float(np.mean(e)), 'wape':float(sum(abs(e))/sum(abs(a))) if sum(abs(a)) else None}


def load_daily(root):
    frames=[]
    for file, date, columns in [('avl_fleet_daily','DATE_DAY',TARGETS[:4]+['num_tails']),
                                ('legs_fleet_daily','dep_date',TARGETS[4:6]),
                                ('quotes_fleet_daily','quote_date',TARGETS[6:])]:
        df=pd.read_parquet(root/'data/processed'/f'{file}.parquet').rename(columns={date:'date'})
        df['date']=pd.to_datetime(df['date'])
        if df['date'].duplicated().any(): raise ValueError(f'Duplicate dates: {file}')
        frames.append(df.set_index('date')[columns])
    result=pd.concat(frames,axis=1).sort_index()
    if result.isna().any().any() or not np.isfinite(result.to_numpy()).all(): raise ValueError('Missing/nonfinite daily data')
    if not result.index.equals(pd.date_range(result.index.min(),result.index.max())): raise ValueError('Daily gaps')
    return result


def baseline(train, dates):
    """Notebook production recipes, refitted on a common cutoff; not saved predictions."""
    from prophet import Prophet
    out=pd.DataFrame(index=dates)
    for col in TARGETS:
        if col in ['aog_rate','umx_rate']:
            monthly=train[col].groupby(train.index.month).mean()
            out[col]=[monthly.get(d.month,train[col].mean()) for d in dates]
        elif col=='cna_rate': out[col]=train[col].mean()
        else:
            quote=col=='daily_quote_count'
            m=Prophet(yearly_seasonality=True, weekly_seasonality=col!='smx_rate',daily_seasonality=False,
                      seasonality_mode='multiplicative' if quote else 'additive',
                      changepoint_prior_scale=.05 if quote or col=='smx_rate' else .1,
                      interval_width=.8,uncertainty_samples=0)
            m.fit(pd.DataFrame({'ds':train.index,'y':train[col].values}))
            out[col]=m.predict(pd.DataFrame({'ds':dates}))['yhat'].values
    # Common operational constraints for both candidates; save unconstrained baseline too.
    return out


def constrain(df):
    out=df.copy()
    for col in TARGETS: out[col]=out[col].clip(0,1 if col.endswith('_rate') else None)
    return out


def curve_bins(quotes):
    q=quotes[(quotes.yield_per_eft>=7000)&(quotes.yield_per_eft<=14750)].copy()
    q['yield_mid']=(q.yield_per_eft//500)*500+250
    qc=q.groupby(['quote_date','yield_mid']).size().groupby('yield_mid').mean()
    c=quotes[(quotes.final_yield>=5000)&(quotes.final_yield<=20000)].copy()
    c['yield_mid']=(c.final_yield//1000)*1000+500
    cv=c.groupby('yield_mid').booked.agg(['mean','size'])
    cv=cv[(cv['size']>=10)&(cv.index>=7500)]
    if len(qc)<3 or len(cv)<3: raise ValueError('Insufficient historical curve bins')
    return qc,cv


def fit_curves(quotes):
    from scipy.optimize import curve_fit
    from statsmodels.nonparametric.smoothers_lowess import lowess
    qc,cv=curve_bins(quotes)
    xy=lowess(qc.values,qc.index.values,frac=.5,return_sorted=True)
    y=xy[:,1]/np.interp(10784,xy[:,0],xy[:,1])
    (a,b),_=curve_fit(lambda x,a,b:a*np.exp(-b*x),cv.index.values/1000,cv['mean'].values,
                      p0=[.8,.15],bounds=([0,0],[np.inf,np.inf]),maxfev=10000)
    return {'x':xy[:,0].tolist(),'multiplier':y.tolist(),'a':float(a),'b':float(b)}


def demand(curve, price, quotes):
    m=np.interp(price,curve['x'],curve['multiplier'])
    if 'a' in curve: c=curve['a']*np.exp(-curve['b']*np.asarray(price)/1000)
    else: c=np.interp(price,curve['x'],curve['conversion'])
    return quotes*m*np.clip(c,0,1)


def solve(curve, quotes, capacity):
    from scipy.optimize import brentq
    if capacity<=0: return None,'DNQ_zero_supply'
    f=lambda p:float(demand(curve,p,quotes))-capacity
    if f(7000)<=0:return 7000.,'demand_below_floor'
    if f(15000)>=0:return 15000.,'demand_above_ceiling'
    return float(brentq(f,7000,15000,xtol=1.)),'solved'


def supply(df, tails):
    # Same current-engine convention: non-program includes OD, separate OD adjustment zero.
    return np.maximum(0,tails*(1-df[TARGETS[:4]].sum(axis=1))*1.06-df.program_live_legs-df.non_program_live_legs)


def make_request(train, dates, historical_quotes):
    if train.index.max() >= min(dates): raise ValueError('Training overlaps forecast horizon')
    qc,cv=curve_bins(historical_quotes)
    return {'version':VERSION,'cutoff':str(train.index.max().date()),
            'definitions':{'rates':'fraction of fleet unavailable; four separate rate forecasts',
                           'legs':'daily flight legs; non-program includes OD',
                           'daily_quote_count':'enquiries by enquiry date, not departure date'},
            'daily_history':train[TARGETS].reset_index().assign(date=lambda d:d.date.dt.strftime('%Y-%m-%d')).to_dict('records'),
            'quote_count_bins':[{'yield':float(x),'mean_count_on_present_days':float(y)} for x,y in qc.items()],
            'conversion_bins':[{'yield':float(x),'conversion':float(row['mean']),'count':int(row['size'])} for x,row in cv.iterrows()],
            'forecast_dates':[str(d.date()) for d in dates], 'curve_yields':GRID,
            'normalization_yield':10784}


class DailyPrediction(BaseModel):
    date:str
    aog_rate:float
    smx_rate:float
    umx_rate:float
    cna_rate:float
    program_live_legs:float
    non_program_live_legs:float
    daily_quote_count:float

class CurvePoint(BaseModel):
    yield_usd:float
    quote_multiplier:float
    conversion_probability:float

class ForecastBundle(BaseModel):
    daily:list[DailyPrediction]
    curve:list[CurvePoint]


def validate_llm(bundle, request):
    df=pd.DataFrame(bundle['daily'])
    if df['date'].tolist()!=request['forecast_dates']:raise ValueError('LLM dates missing, reordered or duplicated')
    vals=df[TARGETS].to_numpy(float)
    if not np.isfinite(vals).all() or (vals<0).any() or (df[TARGETS[:4]]>1).any().any():raise ValueError('Invalid LLM forecast values')
    c=pd.DataFrame(bundle['curve'])
    if c.yield_usd.tolist()!=GRID:raise ValueError('Wrong LLM yield grid')
    if not np.isfinite(c.to_numpy(float)).all() or (c.quote_multiplier<0).any() or not c.conversion_probability.between(0,1).all():raise ValueError('Invalid LLM curve')
    norm=float(np.interp(10784,GRID,c.quote_multiplier))
    if norm<=0:raise ValueError('Cannot normalize LLM multiplier')
    curve={'x':GRID,'multiplier':(c.quote_multiplier/norm).tolist(),'conversion':c.conversion_probability.tolist()}
    df['date']=pd.to_datetime(df.date)
    return df.set_index('date')[TARGETS],curve


def llm_forecast(request, cache, model, allow_paid, max_output_tokens):
    prompt=('Forecast all requested daily targets using ONLY this historical input. Also estimate the quote-count multiplier '
            'and observational booking conversion at each requested yield. Return dates and yields in the exact requested order. '
            'Rates and probabilities must be in [0,1], counts nonnegative; do not include explanations. '
            'The multiplier is relative to yield 10784. Conversion is observational, not a causal estimate.\n'+json.dumps(request))
    key=sha256((model+prompt+str(max_output_tokens)).encode()).hexdigest()
    path=cache/f'{key}.json'
    if path.exists():record=json.loads(path.read_text())
    else:
        if not allow_paid:raise ValueError('No cached LLM response; --allow-paid is required')
        from openai import OpenAI
        start=time.monotonic()
        # No automatic retries: avoid hidden repeat charges and record explicit failures.
        with OpenAI(max_retries=0,timeout=180) as client:
            response=client.responses.parse(model=model,input=prompt,text_format=ForecastBundle,
                                            max_output_tokens=max_output_tokens,store=False)
        record={'model':model,'request_hash':key,'response_id':response.id,'latency_seconds':time.monotonic()-start,
                'usage':response.usage.model_dump() if response.usage else {},
                'bundle':response.output_parsed.model_dump() if response.output_parsed else None}
        write_json(path,record) # Save even invalid/refused output: do not silently retry it.
    if record['bundle'] is None:raise ValueError('LLM response incomplete or refused; cached for inspection')
    df,curve=validate_llm(record['bundle'],request)
    return df,curve,record


def evaluate(name, pred, actual, curve, reference_curve, tails, hold_quotes):
    errors={c:metrics(actual[c],pred[c]) for c in TARGETS}
    ps=supply(pred,tails); actual_supply=supply(actual,tails)
    errors['remaining_supply_proxy']=metrics(actual_supply,ps)
    prices=[]
    for i,day in enumerate(pred.index):
        price,status=solve(curve,float(pred.loc[day,'daily_quote_count']),float(ps.iloc[i]))
        # Reference uses realized component counts but TRAIN-only current curve; not an optimal-price label.
        reference,refstatus=solve(reference_curve,float(actual.loc[day,'daily_quote_count']),float(actual_supply.iloc[i]))
        prices.append({'date':str(day.date()),'candidate':name,'yield':price,'status':status,
                       'reference_yield':reference,'reference_status':refstatus})
    paired=[r for r in prices if r['yield'] is not None and r['reference_yield'] is not None]
    price_metrics={'status_agreement':sum(r['status']==r['reference_status'] for r in prices)/len(prices),
                   'dnq_disagreement':sum((r['status']=='DNQ_zero_supply')!=(r['reference_status']=='DNQ_zero_supply') for r in prices)/len(prices),
                   'paired_non_dnq_dates':len(paired),
                   'yield_mae_vs_reference':float(np.mean([abs(r['yield']-r['reference_yield']) for r in paired])) if paired else None}
    cv=hold_quotes[(hold_quotes.final_yield>=7500)&(hold_quotes.final_yield<=15000)]
    if len(cv):
        p=curve['a']*np.exp(-curve['b']*cv.final_yield.to_numpy()/1000) if 'a' in curve else np.interp(cv.final_yield,curve['x'],curve['conversion'])
        p=np.clip(p,1e-9,1-1e-9); y=cv.booked.to_numpy()
        price_metrics.update(conversion_rows=len(cv),conversion_brier=float(np.mean((p-y)**2)),
                             conversion_log_loss=float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))))
    # Descriptive holdout bin shape, not causal price elasticity.
    hq=hold_quotes[(hold_quotes.yield_per_eft>=7000)&(hold_quotes.yield_per_eft<=14750)].copy()
    hq['yield_mid']=(hq.yield_per_eft//500)*500+250
    bins=hq.groupby(['quote_date','yield_mid']).size().groupby('yield_mid').mean()
    if len(bins)>=3:
        norm=float(np.interp(10784,bins.index,bins.values))
        if norm>0:
            price_metrics['quote_multiplier_bins']=len(bins)
            price_metrics['quote_multiplier_bin_mae']=float(np.mean(abs(np.interp(bins.index,curve['x'],curve['multiplier'])-bins.values/norm)))
    return {'forecast_errors':errors,'pricing_diagnostics':price_metrics},prices


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--origins',nargs='+',default=['2025-06-30','2025-09-30','2025-11-30'])
    parser.add_argument('--horizon',type=int,default=14)
    parser.add_argument('--llm',action='store_true')
    parser.add_argument('--allow-paid',action='store_true')
    parser.add_argument('--model',default='gpt-5.5')
    parser.add_argument('--max-calls',type=int,default=3)
    parser.add_argument('--max-output-tokens',type=int,default=8000)
    args=parser.parse_args()
    if not 1<=args.horizon<=31:parser.error('horizon must be 1–31 days')
    if args.llm and len(args.origins)>args.max_calls:parser.error('Origins exceed max-calls (conservative cap includes cached requests)')
    args.out.mkdir(parents=True,exist_ok=True);cache=args.out/'llm_cache';cache.mkdir(exist_ok=True)
    daily=load_daily(args.root)
    q=pd.read_parquet(args.root/'data/processed/quotes_deduped_enriched.parquet')
    for col in ['quote_date','dep_date']:q[col]=pd.to_datetime(q[col])
    results=[]; all_prices=[]; failures=[]
    for origin in args.origins:
        cutoff=pd.Timestamp(origin);dates=pd.date_range(cutoff+timedelta(days=1),periods=args.horizon)
        train=daily.loc[:cutoff];actual=daily.reindex(dates)
        if len(train)<365 or actual.isna().any().any():raise ValueError('Need >=365 training days and complete held-out actuals')
        # Departure maturity is a proxy: source does not record when final outcome became known.
        mature=q[(q.quote_date<=cutoff)&(q.dep_date<=cutoff)]
        hold=q[(q.quote_date>cutoff)&(q.quote_date<=dates[-1])&(q.dep_date<=dates[-1])]
        request=make_request(train,dates,mature)
        write_json(args.out/f'request_{origin}.json',request)
        ref=fit_curves(mature)
        raw=baseline(train,dates);raw.to_csv(args.out/f'baseline_raw_{origin}.csv')
        pred=constrain(raw)
        naive=pd.DataFrame({c:[float(train[c].iloc[-7+(i%7)]) for i in range(len(dates))] for c in TARGETS},index=dates)
        candidates=[('current_refit',pred,ref),('seasonal_naive',constrain(naive),ref)]
        if args.llm:
            try:
                lp,lc,record=llm_forecast(request,cache,args.model,args.allow_paid,args.max_output_tokens)
                write_json(args.out/f'llm_usage_{origin}.json',{k:v for k,v in record.items() if k!='bundle'})
                candidates += [('llm_forecasts_current_curves',lp,ref),('current_forecasts_llm_curves',pred,lc),('llm_full',lp,lc)]
            except Exception as exc:
                failures.append({'origin':origin,'error_type':type(exc).__name__,'message':'LLM unavailable or invalid; inspect local cache. No fallback substituted.'})
        # Known-at-origin fleet size used for all approaches and reference proxy.
        tails=float(train.num_tails.iloc[-1])
        for name,prediction,curve in candidates:
            evaluation,prices=evaluate(name,prediction,actual,curve,ref,tails,hold)
            results.append({'origin':origin,'candidate':name,**evaluation});all_prices.extend(prices)
            prediction.to_csv(args.out/f'predictions_{origin}_{name}.csv')
        print(f'Completed {origin}: {len(candidates)} candidates',flush=True)
    sources={p.name:sha256(p.read_bytes()).hexdigest() for p in (args.root/'data/processed').glob('*.parquet') if p.stem in ['avl_fleet_daily','legs_fleet_daily','quotes_fleet_daily','quotes_deduped_enriched']}
    write_json(args.out/'results.json',{'version':VERSION,'origins':args.origins,'horizon':args.horizon,'source_hashes':sources,'code_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
                                      'llm_status':'not_run' if not args.llm else ('incomplete' if failures else 'completed'),
                                      'failures':failures,'results':results})
    pd.DataFrame(all_prices).to_csv(args.out/'pricing_diagnostics.csv',index=False)
    aggregated={}
    for candidate in sorted({r['candidate'] for r in results}):
        subset=[r for r in results if r['candidate']==candidate]
        aggregated[candidate]={}
        for target in TARGETS+['remaining_supply_proxy']:
            ms=[r['forecast_errors'][target] for r in subset];n=sum(m['n'] for m in ms)
            aggregated[candidate][target]={'n':n,'mae':sum(m['mae']*m['n'] for m in ms)/n,
                'rmse':math.sqrt(sum(m['rmse']**2*m['n'] for m in ms)/n)}
    write_json(args.out/'aggregate_metrics.json',aggregated)
    lines=['# Forecast benchmark', '', 'LLM results: '+('NOT RUN (no paid calls)' if not args.llm else ('INCOMPLETE' if failures else 'completed')), '',
           'Retrospective rolling-origin test. Lower MAE/RMSE is better. Pricing reference is NOT an optimal-price label.', '',
           '| Origin | Candidate | Target | MAE | RMSE |', '|---|---|---|---:|---:|']
    for r in results:
        for target,m in r['forecast_errors'].items():lines.append(f"| {r['origin']} | {r['candidate']} | {target} | {m['mae']:.4f} | {m['rmse']:.4f} |")
    lines += ['', 'No revenue winner established. Compare the same folds only; invalid LLM folds are reported, not replaced.',
              'Limitations: current recipes were developed using these historical years; this is not an untouched final holdout. Final booking outcomes use departure maturity as a proxy for availability. Final yield can contain realized revenue. Conversion scores are observational and selected by yield availability. No causal elasticity or revenue uplift is established. Historical processed tables are not archived as-of snapshots. Pricing uses a fixed 1.06 legs/tail, origin fleet size, zero separate OD adjustment, and the existing enquiry/departure-date join.']
    lines += ['', '## Aggregate forecast errors', '', '| Candidate | Target | Days | MAE | RMSE |', '|---|---|---:|---:|---:|']
    for candidate, targets in aggregated.items():
        for target, m in targets.items():
            lines.append(f"| {candidate} | {target} | {m['n']} | {m['mae']:.4f} | {m['rmse']:.4f} |")
    (args.out/'report.md').write_text('\n'.join(lines)+'\n')
    if failures: raise SystemExit(2)

if __name__=='__main__':main()
