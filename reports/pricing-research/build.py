"""Build a portable dashboard from checked-in experiment aggregates (no APIs)."""
import json
from pathlib import Path
from hashlib import sha256
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
sources = {
 'automl': 'experiments/automl_grid_v1/comparison_results.json',
 'pilot': 'experiments/synthetic_three_way_v1/aggregate_results.json',
 'robust': 'experiments/synthetic_robustness_v1/aggregate_results.json',
 'historical': 'experiments/gpt55_adaptive_2026-10-14/final_results.json',
 'search': 'experiments/component_selection_complete_2026-10-14/final_results.json',
 'direct': 'experiments/llm_pilot/results.json',
}
data = {k: json.loads((ROOT/v).read_text()) for k,v in sources.items()}
data['sources'] = [{'path':v,'sha256':sha256((ROOT/v).read_bytes()).hexdigest()} for v in sources.values()]
(OUT/'index.html').write_text((OUT/'template.html').read_text().replace('__DATA__',json.dumps(data).replace('</','<\\/')))
(OUT/'source_manifest.json').write_text(json.dumps(data['sources'],indent=2)+'\n')
print('Built reports/pricing-research/index.html')
