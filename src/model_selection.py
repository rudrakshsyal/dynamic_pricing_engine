"""Bounded ML experiment tools. Validation chooses; a frozen final holdout evaluates."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
from src.model_benchmark import (TARGETS, GRID, baseline, constrain, curve_bins, fit_curves,
                                 load_daily, metrics, evaluate, write_json)

ORIGINS = ['2025-06-30', '2025-08-31', '2025-09-30']
FINAL_ORIGIN = '2025-10-31'
HORIZON = 28
CANDIDATES = ['current', 'seasonal_naive', 'monthly_mean', 'rolling_mean',
              'ridge', 'extra_trees', 'xgb_shallow', 'xgb_medium']
CURVES = {'quote_multiplier':['current_lowess','constant_one','shrink_half'],
          'conversion':['current_exponential','constant','isotonic']}
COMPONENTS = TARGETS + list(CURVES)
SEED = 42


def features(values, day):
    """All numerical features precede the target date; future calendar fields are known."""
    a=np.asarray(values,float)
    if len(a)<28:raise ValueError('Need 28 previous observations')
    return [a[-1],a[-7],a[-14],a[-28],a[-7:].mean(),a[-28:].mean(),
            a[-7:].std(),a[-28:].std(),
            np.sin(2*np.pi*day.dayofweek/7),np.cos(2*np.pi*day.dayofweek/7),
            np.sin(2*np.pi*day.dayofyear/365.25),np.cos(2*np.pi*day.dayofyear/365.25),day.month]


def forecast(train, dates, target, model, current=None):
    y=train[target]
    upper=1. if target.endswith('_rate') else np.inf
    if model=='current':return current[target].to_numpy()
    if model=='seasonal_naive':return np.array([y.iloc[-7+i%7] for i in range(len(dates))])
    if model=='monthly_mean':
        means=y.groupby(y.index.month).mean()
        return np.array([means.get(d.month,y.mean()) for d in dates])
    if model=='rolling_mean':return np.repeat(y.iloc[-28:].mean(),len(dates))
    x=np.array([features(y.iloc[:i],y.index[i]) for i in range(28,len(y))])
    labels=y.iloc[28:].to_numpy()
    if model=='ridge':
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.linear_model import Ridge
        estimator=make_pipeline(StandardScaler(),Ridge(alpha=10.))
        estimator.fit(x,labels)
        predict=lambda row:float(estimator.predict(np.asarray([row]))[0])
    elif model=='extra_trees':
        from sklearn.ensemble import ExtraTreesRegressor
        estimator=ExtraTreesRegressor(n_estimators=150,min_samples_leaf=7,max_features=1.,random_state=SEED,n_jobs=2)
        estimator.fit(x,labels)
        predict=lambda row:float(estimator.predict(np.asarray([row]))[0])
    elif model.startswith('xgb_'):
        import xgboost as xgb
        depth,rounds=(2,120) if model=='xgb_shallow' else (4,180)
        estimator=xgb.train({'objective':'reg:squarederror','max_depth':depth,'eta':.04,
                             'min_child_weight':8,'subsample':1.,'colsample_bytree':1.,
                             'seed':SEED,'nthread':2,'tree_method':'hist'},xgb.DMatrix(x,label=labels),num_boost_round=rounds)
        predict=lambda row:float(estimator.predict(xgb.DMatrix(np.asarray([row])))[0])
    else:raise ValueError('Unknown candidate')
    history=y.tolist();output=[]
    for day in dates:
        value=float(np.clip(predict(features(history,day)),0,upper))
        output.append(value);history.append(value) # recursive, never inserts holdout actuals
    return np.asarray(output)


def curve_candidate(quotes, component, name, reference):
    qc,cv=curve_bins(quotes)
    if component=='quote_multiplier':
        if name=='current_lowess':return {k:v for k,v in reference.items() if k in ['x','multiplier']}
        base=np.interp(GRID,reference['x'],reference['multiplier'])
        return {'x':GRID,'multiplier':np.ones(len(GRID)).tolist() if name=='constant_one' else (.5+.5*base).tolist()}
    eligible=quotes[(quotes.final_yield>=7500)&(quotes.final_yield<=15000)]
    if name=='current_exponential':return {'a':reference['a'],'b':reference['b']}
    if name=='constant':return {'conversion_x':GRID,'conversion':[float(eligible.booked.mean())]*len(GRID)}
    from sklearn.isotonic import IsotonicRegression
    iso=IsotonicRegression(increasing=False,y_min=0,y_max=1,out_of_bounds='clip')
    iso.fit(cv.index,cv['mean'],sample_weight=cv['size'])
    return {'conversion_x':GRID,'conversion':iso.predict(GRID).tolist()}


def combine(multiplier, conversion):
    # All candidates use the same evaluation grid when combining non-exponential curves.
    result={'x':GRID,'multiplier':np.interp(GRID,multiplier['x'],multiplier['multiplier']).tolist()}
    if 'a' in conversion:result.update(a=conversion['a'],b=conversion['b'])
    else:result['conversion']=np.interp(GRID,conversion['conversion_x'],conversion['conversion']).tolist()
    return result


def curve_score(quotes, component, curve):
    if component=='conversion':
        q=quotes[(quotes.final_yield>=7500)&(quotes.final_yield<=15000)]
        if q.empty:raise ValueError('No eligible held-out conversion rows')
        p=curve['a']*np.exp(-curve['b']*q.final_yield.to_numpy()/1000) if 'a' in curve else np.interp(q.final_yield,curve['conversion_x'],curve['conversion'])
        p=np.clip(p,1e-9,1-1e-9);y=q.booked.to_numpy()
        return {'n':len(q),'loss':float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))), 'brier':float(np.mean((p-y)**2))}
    q=quotes[(quotes.yield_per_eft>=7000)&(quotes.yield_per_eft<=14750)].copy()
    q['mid']=(q.yield_per_eft//500)*500+250
    bins=q.groupby(['quote_date','mid']).size().groupby('mid').mean()
    if len(bins)<3:raise ValueError('Too few held-out bins')
    normalized=bins.values/np.interp(10784,bins.index,bins.values)
    return {'n':len(bins),'loss':float(np.mean(abs(np.interp(bins.index,curve['x'],curve['multiplier'])-normalized)))}


class Experiment:
    """Only these fixed operations are exposed to the optional coordinator."""
    def __init__(self, root, out):
        self.root=Path(root); self.out=Path(out);self.out.mkdir(parents=True,exist_ok=True)
        self.daily=load_daily(self.root)
        self.quotes=pd.read_parquet(self.root/'data/processed/quotes_deduped_enriched.parquet')
        for c in ['quote_date','dep_date']:self.quotes[c]=pd.to_datetime(self.quotes[c])
        self.scores={};self.selections=None;self.current_cache={};self.audit=[]
        self.manifest={'version':'selection-v1','validation_origins':ORIGINS,'horizon':HORIZON,
                       'final_origin':FINAL_ORIGIN,'seed':SEED,'daily_candidates':CANDIDATES,
                       'curve_candidates':CURVES,'selection_metric':'pooled RMSE for daily targets; pooled log loss for conversion; bin-weighted MAE for multiplier',
                       'source_hashes':{p.name:sha256(p.read_bytes()).hexdigest() for p in (self.root/'data/processed').glob('*.parquet') if p.stem in ['avl_fleet_daily','legs_fleet_daily','quotes_fleet_daily','quotes_deduped_enriched']},
                       'code_sha256':sha256(Path(__file__).read_bytes()).hexdigest()}
        write_json(self.out/'manifest.json',self.manifest)

    def split(self, origin):
        origin=pd.Timestamp(origin);dates=pd.date_range(origin+pd.Timedelta(days=1),periods=HORIZON)
        train=self.daily.loc[:origin];actual=self.daily.reindex(dates)
        if len(train)<365 or actual.isna().any().any():raise ValueError('Insufficient training or holdout coverage')
        mature=self.quotes[(self.quotes.quote_date<=origin)&(self.quotes.dep_date<=origin)]
        test=self.quotes[(self.quotes.quote_date>origin)&(self.quotes.quote_date<=dates[-1])&(self.quotes.dep_date<=dates[-1])]
        return train,actual,mature,test

    def current(self, origin):
        if origin not in self.current_cache:
            train,test,_,_=self.split(origin)
            self.current_cache[origin]=constrain(baseline(train,test.index))
        return self.current_cache[origin]

    def evaluate_component(self, component):
        if self.selections is not None:raise ValueError('Selection already frozen')
        if component not in COMPONENTS:raise ValueError('Component outside approved registry')
        if component in self.scores:return self.scores[component]
        names=CANDIDATES if component in TARGETS else CURVES[component]
        rows=[]
        for name in names:
            folds=[];errors=[];started=time.monotonic()
            for origin in ORIGINS:
                train,actual,mature,hold=self.split(origin)
                try:
                    if component in TARGETS:
                        pred=forecast(train,actual.index,component,name,self.current(origin) if name=='current' else None)
                        m=metrics(actual[component],pred)
                        folds.append({'origin':origin,**m})
                    else:
                        curve=curve_candidate(mature,component,name,fit_curves(mature))
                        folds.append({'origin':origin,**curve_score(hold,component,curve)})
                except Exception as exc:errors.append({'origin':origin,'type':type(exc).__name__,'message':str(exc)[:300]})
            score=None
            if not errors:
                n=sum(f['n'] for f in folds)
                score=(sum(f['rmse']**2*f['n'] for f in folds)/n)**.5 if component in TARGETS else sum(f['loss']*f['n'] for f in folds)/n
            rows.append({'candidate':name,'score':score,'folds':folds,'failures':errors,'seconds':time.monotonic()-started})
        valid=[r for r in rows if r['score'] is not None]
        if not valid:raise RuntimeError('No complete candidate')
        winner=min(valid,key=lambda r:(r['score'],names.index(r['candidate'])))['candidate']
        result={'component':component,'winner':winner,'candidates':rows}
        self.scores[component]=result
        self.audit.append({'tool':'evaluate_component','component':component,'winner':winner})
        write_json(self.out/'validation_scores.json',self.scores)
        print(f'Validation {component}: {winner}',flush=True)
        return result

    def freeze_selection(self):
        if set(self.scores)!=set(COMPONENTS):raise ValueError('Evaluate all components before freezing')
        if any(r['failures'] for component in self.scores.values() for r in component['candidates']):
            raise ValueError('Candidate registry incomplete: resolve training failures before final evaluation')
        if self.selections is None:
            self.selections={c:self.scores[c]['winner'] for c in COMPONENTS}
            write_json(self.out/'frozen_selection.json',{'manifest':self.manifest,'selected':self.selections})
            self.audit.append({'tool':'freeze_selection'})
        return self.selections

    def final_test(self):
        if self.selections is None:raise ValueError('Freeze validation-only selection before accessing final test')
        train,actual,mature,hold=self.split(FINAL_ORIGIN)
        current=self.current(FINAL_ORIGIN)
        selected=pd.DataFrame({c:forecast(train,actual.index,c,self.selections[c],current) for c in TARGETS},index=actual.index)
        reference=fit_curves(mature)
        mult=curve_candidate(mature,'quote_multiplier',self.selections['quote_multiplier'],reference)
        conv=curve_candidate(mature,'conversion',self.selections['conversion'],reference)
        curve=combine(mult,conv)
        results={};prices=[]
        for name,pred,c in [('current',current,reference),('selected_forecasts',selected,reference),('selected_full',selected,curve)]:
            score,rows=evaluate(name,pred,actual,c,reference,float(train.num_tails.iloc[-1]),hold)
            results[name]=score;prices+=rows
            pred.to_csv(self.out/f'final_predictions_{name}.csv')
        actual.to_csv(self.out/'final_actuals.csv')
        table=pd.DataFrame(prices);table.to_csv(self.out/'final_pricing.csv',index=False)
        # Compare price errors on exactly the same non-DNQ dates across every candidate.
        common=set(actual.index.strftime('%Y-%m-%d'))
        for name in results:
            frame=table[table.candidate==name]
            common &= set(frame.loc[frame['yield'].notna()&frame.reference_yield.notna(),'date'])
        for name in results:
            pair=table[(table.candidate==name)&table.date.isin(common)]
            results[name]['pricing_diagnostics']['common_non_dnq_n']=len(pair)
            results[name]['pricing_diagnostics']['common_yield_mae']=float(abs(pair['yield']-pair.reference_yield).mean()) if len(pair) else None
        curves_final={}
        for component in CURVES:
            curves_final[component]={}
            for name in [CURVES[component][0],self.selections[component]]:
                curves_final[component][name]=curve_score(hold,component,curve_candidate(mature,component,name,reference))
        write_json(self.out/'final_results.json',{'selected':self.selections,'results':results,'curve_results':curves_final,
                                               'final_test_days':len(actual),'common_price_dates':sorted(common)})
        self.audit.append({'tool':'final_test','days':len(actual)})
        write_json(self.out/'tool_audit.json',self.audit)
        return results


def build_report(experiment, results, mode):
    lines=['# Component model-selection experiment','',f'Execution: {mode}.',
           'Validation: July 1–28, September 1–28 and October 1–28, 2025. Final test: November 1–28, 2025.',
           'Choices frozen before final-test scoring. This is a historical evaluation, not a new prospective holdout.', '',
           '| Component | Validation winner | Current test RMSE | Selected test RMSE | Error reduction |',
           '|---|---|---:|---:|---:|']
    for c in TARGETS:
        a=results['current']['forecast_errors'][c]['rmse']; b=results['selected_full']['forecast_errors'][c]['rmse']
        lines.append(f'| {c} | {experiment.selections[c]} | {a:.5f} | {b:.5f} | {(1-b/a)*100:.1f}% |')
    lines+=['','Rates are fractions; multiply by 100 for percentage points. Positive reduction is better.',
            '', 'Curve selections: '+json.dumps({c:experiment.selections[c] for c in CURVES}),
            '', '## Pricing diagnostics', '', '| Pipeline | Supply-proxy RMSE | Status agreement | DNQ disagreement | Common-date price MAE |', '|---|---:|---:|---:|---:|']
    for name,r in results.items():
        p=r['pricing_diagnostics'];mae=p['common_yield_mae']
        lines.append(f"| {name} | {r['forecast_errors']['remaining_supply_proxy']['rmse']:.3f} | {p['status_agreement']:.1%} | {p['dnq_disagreement']:.1%} | {mae if mae is not None else 'N/A'} (n={p['common_non_dnq_n']}) |")
    lines+=['','No revenue or causal pricing improvement is established. The pricing reference uses actual component inputs and the current train-only demand curve.',
            'The test does not choose a new winner after observing final results. The best validation candidate is not necessarily the best future model.',
            'Final extracts, maturity approximations, mixed realized/quoted yields, fixed fleet productivity and enquiry/departure-date mismatch remain limitations.']
    (experiment.out/'report.md').write_text('\n'.join(lines)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if (args.out/'manifest.json').exists():p.error('Use a new output directory to preserve the frozen experiment')
    import xgboost  # fail early if the required OpenMP runtime is unavailable
    experiment=Experiment(args.root,args.out)
    for component in COMPONENTS:experiment.evaluate_component(component)
    experiment.freeze_selection();results=experiment.final_test()
    build_report(experiment,results,'deterministic runner invoking the same bounded tools as the optional LLM coordinator; no paid calls')

if __name__=='__main__':main()
