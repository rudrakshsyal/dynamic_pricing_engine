from pathlib import Path
import json
import numpy as np
import pandas as pd
from src.synthetic_benchmark import load
p=Path('experiments/automl_grid_v1'); a=json.loads((p/'comparison_results.json').read_text());f=pd.read_csv(p/'evaluation/predictions.csv');prices=pd.read_csv(p/'comparison_pricing.csv')
assert len(a)==45
for path in f.path.unique():
 daily,_=load(Path('experiments/synthetic_fleet_v1')/path)
 for h in [14,28,90]:
  r=next(r for r in a if (r['path'],r['candidate'],r['horizon'])==(path,'automl',h))
  frames=[];squares=[]
  for origin,g in f[(f.path==path)&(f.candidate=='frozen_agent')].groupby('origin'):
   g=g.head(h);frames.append(g);tails=daily.loc[:origin].num_tails.iloc[-1]
   def supply(prefix):
    rates=sum(g[prefix+c] for c in ['aog_rate','smx_rate','umx_rate','cna_rate'])
    return np.maximum(0,tails*(1-rates)*1.06-g[prefix+'program_live_legs']-g[prefix+'non_program_live_legs'])
   squares.extend((supply('actual_')-supply('predicted_'))**2)
  assert np.isclose(np.sqrt(np.mean(squares)),r['forecast_errors']['remaining_supply_proxy']['rmse'])
  allrows=pd.concat(frames)
  for c,m in r['forecast_errors'].items():
   if c!='remaining_supply_proxy':assert np.isclose(np.sqrt(np.mean((allrows['actual_'+c]-allrows['predicted_'+c])**2)),m['rmse'])
  groups=prices[(prices.path==path)&(prices.horizon==h)].groupby('candidate')
  valid=[]
  for _,g in groups:
   z=g[g['yield'].notna()&g.reference_yield.notna()];valid.append(set(zip(z.origin,z.date)))
  common=set.intersection(*valid)
  for name,g in groups:
   z=g[[k in common for k in zip(g.origin,g.date)]]
   m=next(r for r in a if (r['path'],r['candidate'],r['horizon'])==(path,name,h))
   assert len(z)==m['common_price_n']
   assert np.isclose(abs(z['yield']-z.reference_yield).mean(),m['common_price_mae'])
print('Independent checks passed: all AutoML component/supply RMSEs and all matched three-way price MAEs.')
