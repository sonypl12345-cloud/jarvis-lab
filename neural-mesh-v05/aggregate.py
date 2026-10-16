#!/usr/bin/env python3
"""Strict independent 2-runner aggregation: reject missing, corrupted or overlapping shards."""
import hashlib
import json
from pathlib import Path
EXPECTED_FULL="42ba48a98917fb299da54e1ca078b574e32d3e2fa59c1585942129e85ae9155f"
EXPECTED={
(0,128):"6a1fddeaf716336a9aea024f045c91ac2efb558062baf5586fc5288f39981813",
(128,256):"3d4c1485e1a5f20489654a3710030e7b0a3292f6de559640f67685bf660d348e",
(0,256):EXPECTED_FULL}
def validate(res,bounds):
 assert isinstance(res,dict) and res.get("schema")=="GENESIS_NEURAL_MESH_PARALLEL/0.5","SCHEMA"
 assert (res["start"],res["end"])==bounds,"WRONG_RANGE"
 assert res["cases"]==bounds[1]-bounds[0],"WRONG_CASE_COUNT"
 assert res["repetitions"]==20000,"REPETITIONS_MISMATCH"
 assert res["model_npz_sha256"]=="f156378799b6a67ae8e6c754f00e302785fcc130fa914d4c830747655aaa7e00","MODEL_MISMATCH"
 assert res["packed_weights_sha256"]=="674a35040841dc2b7bb7e227327a78ffa4a3c9a03fd16d0fd24cebb5eadf1577","WEIGHTS_MISMATCH"
 data=bytes.fromhex(res["predictions_hex"])
 assert len(data)==res["cases"] and set(data)<={0,1},"INVALID_PREDICTIONS"
 assert hashlib.sha256(data).hexdigest()==res["prediction_sha256"]==EXPECTED[bounds],"BAD_DIGEST"
 assert res["positive_count"]==sum(data),"BAD_POSITIVE_COUNT"
 assert res["compute_ms"]>0,"BAD_TIMING"
 return data
def merge(a,b,base):
 d1=validate(a,(0,128));d2=validate(b,(128,256));d0=validate(base,(0,256))
 assert hashlib.sha256(d1+d2).hexdigest()==EXPECTED_FULL,"MERGE_SHA_MISMATCH"
 assert d1+d2==d0,"SINGLE_AND_SHARDS_DISAGREE"
 max_shard_ms=max(a["compute_ms"],b["compute_ms"])
 return {"verdict":"PASS_TWO_INDEPENDENT_GITHUB_RUNNERS","total_cases":256,
 "full_sha256":EXPECTED_FULL,"positives":sum(d1+d2),
 "baseline_compute_ms":base["compute_ms"],"parallel_slowest_compute_ms":max_shard_ms,
 "compute_only_speedup":round(base["compute_ms"]/max_shard_ms,3),
 "disclaimer":"Compute-only speedup, NOT GitHub Actions end-to-end speedup or cross-cloud Supabase + GitHub proof"}
def main():
 root=Path("artifacts")
 data={key:json.loads((root/("mesh-"+key)/"result.json").read_text()) for key in ["left","right","baseline"]}
 result=merge(data["left"],data["right"],data["baseline"])
 print("GENESIS_NEURAL_MESH_V05_MERGE "+json.dumps(result,sort_keys=True))
 Path("merge_result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
