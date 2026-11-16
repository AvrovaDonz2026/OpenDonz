#!/usr/bin/env python3
"""Extract paired GF180 area and diagnostic timing without physical-fit claims."""
import json,pathlib,re
B=pathlib.Path(__file__).resolve().parent
result={}
for name in ('baseline','stub'):
 log=(B/name/'gf180.log').read_text()
 area=re.findall(r'Chip area for (?:top )?module.*?:\s*([0-9.]+)',log)
 if not area:area=re.findall(r'Chip area for module.*?([0-9]+\.[0-9]+)',log)
 assert area,(name,'missing mapped area')
 assert 'End of script.' in log,(name,'synthesis incomplete')
 row=dict(cell_area_um2=float(area[-1]),macro_count=49,macro_area_mm2=49*301.300*515.810/1e6)
 row['cell_area_mm2']=row['cell_area_um2']/1e6
 row['otbn_raw_mm2']=row['cell_area_mm2']+row['macro_area_mm2']
 row['soc_lower_bound_mm2']=row['otbn_raw_mm2']+0.931858+0.855116
 row['excess_over_half_core_mm2']=row['soc_lower_bound_mm2']-5.020056
 timing=B/name/'timing.log'
 if timing.exists():
  m=re.search(r'core period_min = ([0-9.]+) fmax = ([0-9.]+)',timing.read_text())
  if m:row.update(diagnostic_core_min_period_ns=float(m[1]),diagnostic_core_fmax_mhz=float(m[2]))
 result[name]=row
result['cell_saving_mm2']=result['baseline']['cell_area_mm2']-result['stub']['cell_area_mm2']
result['cell_saving_percent']=100*result['cell_saving_mm2']/result['baseline']['cell_area_mm2']
result['historical_baseline_cell_mm2']=4.268281024
result['half_core_mm2']=5.020056
(B/'results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
