from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent
xs=json.loads((ROOT/"reports"/"candidate_level_fusion_v3_0.json").read_text())
issues=[]
for x in xs:
    if not x["source_cutoff"] < x["date"]: issues.append(("cutoff",x["date"],x["house"]))
    if x["active"] and x.get("shadow_status",{}).get("reason") != "PROBATION_SURVIVED": issues.append(("activation",x["date"],x["house"]))
print({"checked":len(xs),"active":sum(bool(x["active"]) for x in xs),"issues":issues,"status":"PASS" if not issues else "FAIL"})
raise SystemExit(1 if issues else 0)
