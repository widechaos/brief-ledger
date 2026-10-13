"""Author-written diagnostic, not a customer benchmark."""
import json
import statistics
import time
from pathlib import Path
from ledger import Reviewer, lexical_ranking
root=Path(__file__).parent
sample=json.loads((root/'web/sample.json').read_text())
cases=json.loads((root/'docs/diagnostic-cases.json').read_text())
reviewer=Reviewer()
results=[]
for case in cases:
    payload={'brief':sample['brief'],'requests':[{'text':case['text'],'quantity':1,'unit':'item'}]}
    start=time.perf_counter();r=reviewer.analyze(payload)['results'][0];elapsed=(time.perf_counter()-start)*1000
    actual=None if r['signal']=='No clear match' else r['candidates'][0]['source']['id']
    lexical='B'+str(1+lexical_ranking(case['text'],[b['text'] for b in sample['brief']])[0])
    results.append({**case,'actual':actual,'signal':r['signal'],'score':r['score'],'margin':r['margin'],'correct':actual==case['expected'],'lexical_top1':lexical,'latency_ms':round(elapsed,2)})
related=[r for r in results if r['expected']]
report={'purpose':'12 author-written English diagnostics using a fictional copywriting brief; not independent or paid-user validation', 'cases':results,'correct_including_abstention':sum(r['correct'] for r in results),'total':len(results),'related_top1':sum(r['actual']==r['expected'] for r in related),'related_total':len(related),'lexical_related_top1':sum(r['lexical_top1']==r['expected'] for r in related),'warm_median_ms':round(statistics.median(r['latency_ms'] for r in results[1:]),2),'cold_first_ms':results[0]['latency_ms'],'notes':'Model loading excluded. Baseline is simple token Jaccard with no abstention; compare only related-case top1. Threshold 0.40 and gap 0.08 are heuristics, not calibrated.'}
(root/'docs/evaluation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
