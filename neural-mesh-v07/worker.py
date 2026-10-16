#!/usr/bin/env python3
"""GENESIS Neural Mesh v0.7 — eight frozen learned experts, no network or secrets."""
import argparse
import base64
import hashlib
import json
import math
import os
import struct
import time
from pathlib import Path

DATA_FILE=Path(__file__).with_name("experts.json")
EXPECTED_COMBINED="f457b3cd525b4c48a49d38d5d5e6a3393e4a8f0ded846b3b5b259f958fe720d6"
ROLES={"baseline":range(8),"left":range(4),"right":range(4,8)}
ALLOWED_REPS=(500, 10000)

def points(expert):
    r=[]
    for i in range(128):
        d=hashlib.sha256(f"genesis-neural-mesh-v07-expert-{expert}-case-{i}".encode()).digest()
        u,v=struct.unpack("<HH",d[:4])
        r.append((u*4.0/65535-2.0,v*4.0/65535-2.0))
    return r

def predict(weights,x,y):
    h=[math.tanh(weights[2*i]*x+weights[2*i+1]*y+weights[24+i]) for i in range(12)]
    return int(sum(weights[36+i]*h[i] for i in range(12))+weights[48] > 0.0)

def run(role,reps):
    assert role in ROLES and reps in ALLOWED_REPS
    data=json.loads(DATA_FILE.read_text())
    assert data["schema"]=="GENESIS_NEURAL_MESH_EIGHT_FROZEN_EXPERTS/0.7"
    assert len(data["models"])==8
    loaded={}
    for i in ROLES[role]:
        model=data["models"][i]
        assert model["id"]==i
        raw=base64.b64decode(model["weights_b64"],validate=True)
        assert len(raw)==196 and hashlib.sha256(raw).hexdigest()==model["packed_sha256"],f"WEIGHTS_TAMPER_{i}"
        loaded[i]=(model,struct.unpack("<49f",raw),points(i))
    start=time.perf_counter_ns()
    for _ in range(reps):
        outputs={i:bytes(predict(w,x,y) for x,y in pts) for i,(m,w,pts) in loaded.items()}
    ms=(time.perf_counter_ns()-start)/1e6
    experts=[]
    for i,(m,w,pts) in loaded.items():
        out=outputs[i]
        assert len(out)==128
        assert hashlib.sha256(out).hexdigest()==m["oracle_output_sha256"],f"BAD_ORACLE_{i}"
        assert sum(out)==m["expected_positives"],f"BAD_POSITIVES_{i}"
        experts.append({"id":i,"oracle_sha256":m["oracle_output_sha256"],"npz_sha256":m["npz_sha256"],"packed_sha256":m["packed_sha256"],"outputs_hex":out.hex()})
    if role=="baseline":
        assert hashlib.sha256(b"".join(outputs[i] for i in range(8))).hexdigest()==EXPECTED_COMBINED
    return {"schema":"GENESIS_NEURAL_MESH_EIGHT_RUN/0.7","role":role,"repetitions":reps,
            "experts":experts,"expert_count":len(experts),"compute_ms":round(ms,3),
            "runner_name":os.environ.get("RUNNER_NAME","local"),"runner_os":os.environ.get("RUNNER_OS","local"),
            "verified_local_oracles":True}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--role",required=True,choices=list(ROLES))
    p.add_argument("--reps",type=int,required=True,choices=ALLOWED_REPS)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    out=run(a.role,a.reps)
    Path(a.output).write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
    print("GENESIS_MESH_V07_RESULT "+json.dumps({k:v for k,v in out.items() if k!="experts"},sort_keys=True))
if __name__=="__main__":
    main()
