#!/usr/bin/env python3
"""GENESIS Neural Mesh v0.7: independently validate two expert groups, no baseline gate."""
import argparse
import hashlib
import json
from pathlib import Path

TOTAL_SHA="f457b3cd525b4c48a49d38d5d5e6a3393e4a8f0ded846b3b5b259f958fe720d6"
EXPECTED=({"id":0,"sha":"cc92c3cdd6cca3987863ce1c1512d145d3acc288b79787eaa7f9060f49cabf03"},
{"id":1,"sha":"5ac1363bcb86fafc7b1892ebeef51af189dfc0594a85dd5e25d92f183df76c84"},
{"id":2,"sha":"9a6094ab8f4dd0118927d7a22a6af9e375b26830a6364d517e5d6629a38cebe2"},
{"id":3,"sha":"cd77af0c465d861e0ed092ba7b9b660fc53b9b6f548c91ccf7baba7785e0d4c5"},
{"id":4,"sha":"6f5b32a90c5216fd7bf205bfce9cf4bd37c5d664dc0f03f8b0d3add76dc435c5"},
{"id":5,"sha":"d705c9669850180d5dd7d20747bd7ba0da8aeda69f65f918631db1c3c92e3821"},
{"id":6,"sha":"564cd3c48eb774f1f0facf2b9e2175e36c2dea6cdb0b418743bb0db083775a47"},
{"id":7,"sha":"d7668b372888fe7109177e9b8c3c58c015b4edc2239f01a4ccfe05cbc6c56cbe"})
def check(doc,role,reps):
    assert doc.get("schema")=="GENESIS_NEURAL_MESH_EIGHT_RUN/0.7","SCHEMA"
    assert doc.get("role")==role and doc.get("repetitions")==reps,"ROLE_OR_REPS"
    assert doc.get("verified_local_oracles") is True,"MODEL_UNVERIFIED"
    expect=list(range(4)) if role=="left" else list(range(4,8))
    assert doc.get("expert_count")==len(expect),"MODEL_COUNT"
    assert [x["id"] for x in doc["experts"]]==expect,"MODEL_ORDER"
    assert float(doc["compute_ms"])>0,"INVALID_TIME"
    assert isinstance(doc.get("runner_name"),str) and len(doc["runner_name"])>0,"INVALID_RUNNER"
    outputs=[]
    for part,i in zip(doc["experts"],expect):
        value=bytes.fromhex(part["outputs_hex"])
        assert len(value)==128 and set(value)<=set((0,1)),"INVALID_OUTPUT"
        assert part["oracle_sha256"]==EXPECTED[i]["sha"],"ORACLE_LABEL"
        assert hashlib.sha256(value).hexdigest()==EXPECTED[i]["sha"],"DIGEST_MISMATCH"
        outputs.append(value)
    return b"".join(outputs)
def merge(left,right,reps):
    a=check(left,"left",reps);b=check(right,"right",reps)
    assert left["runner_name"]!=right["runner_name"],"NOT_INDEPENDENT_RUNNERS"
    merged=a+b
    assert len(merged)==1024 and hashlib.sha256(merged).hexdigest()==TOTAL_SHA,"BAD_MERGE"
    return {"verdict":"PASS_EIGHT_LEARNED_EXPERTS_TWO_CLOUD_CPUS","repetitions":reps,
    "predictions":1024,"exact_sha256":TOTAL_SHA,"positives":sum(merged),
    "parallel_compute_ms":max(left["compute_ms"],right["compute_ms"]),
    "runners":[left["runner_name"],right["runner_name"]],
    "end_to_end_speedup":"MEASURE_FROM_ACTIONS_JOB_TIMESTAMPS"}
def main():
    p=argparse.ArgumentParser();p.add_argument("--reps",required=True,type=int,choices=[500,10000]);a=p.parse_args()
    root=Path("artifacts")
    data={x:json.loads((root/("mesh-"+x)/"result.json").read_text()) for x in ("left","right")}
    res=merge(data["left"],data["right"],a.reps)
    Path("merged.json").write_text(json.dumps(res,sort_keys=True,indent=2)+"\n")
    print("GENESIS_MESH_V07_MERGE "+json.dumps(res,sort_keys=True))
if __name__=="__main__":
    main()
