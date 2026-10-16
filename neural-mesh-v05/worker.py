#!/usr/bin/env python3
"""GENESIS Neural Mesh v0.5: frozen neural model on independent Actions runners."""
import argparse
import base64
import hashlib
import json
import math
import os
import platform
import struct
import time
from pathlib import Path

SCHEMA="GENESIS_NEURAL_MESH_PARALLEL/0.5"
MODEL_SHA256="f156378799b6a67ae8e6c754f00e302785fcc130fa914d4c830747655aaa7e00"
WEIGHTS_SHA256="674a35040841dc2b7bb7e227327a78ffa4a3c9a03fd16d0fd24cebb5eadf1577"
WEIGHTS_B64="DlMOwKDMiz17rA+9bwFKP2f1WL4D42s9/DQHQGLqiL0eCts+MZmrvb/+gD/por29OJslQLV0ir1t4Pm/ereQPcAzCsBEwYo9Kg5EPxrn3b18lRQ/hpqKPygwAsCne5E9iVZavMSSgT8gQVs/Kp4jPDVh/b6aNPO8BE6oPOBIvrtqkky88QmeveohSj+RgNm7IGfCv2lnDL1NE4i+rdXRP+lJkD5PyCg/bBfKP4or8b/JgsW/SVvlPohKpj/RoD3ADG8ZPg=="
EXPECTED={
 (0,128):"6a1fddeaf716336a9aea024f045c91ac2efb558062baf5586fc5288f39981813",
 (128,256):"3d4c1485e1a5f20489654a3710030e7b0a3292f6de559640f67685bf660d348e",
 (0,256):"42ba48a98917fb299da54e1ca078b574e32d3e2fa59c1585942129e85ae9155f",
}
def load_weights():
 raw=base64.b64decode(WEIGHTS_B64,validate=True)
 assert len(raw)==196 and hashlib.sha256(raw).hexdigest()==WEIGHTS_SHA256
 return struct.unpack("<49f",raw)
def infer(x,y,w):
 h=[math.tanh(w[2*i]*x+w[2*i+1]*y+w[24+i]) for i in range(12)]
 return int(sum(w[36+i]*h[i] for i in range(12))+w[48]>=0)
def points(a,b):
 result=[]
 for i in range(a,b):
  digest=hashlib.sha256(("genesis-neural-mesh-v02-case-"+str(i)).encode()).digest()
  u,v=struct.unpack("<HH",digest[:4])
  result.append((u*4.0/65535-2,v*4.0/65535-2))
 return result
def run(a,b,repeats):
 assert (a,b) in EXPECTED and isinstance(repeats,int) and 1<=repeats<=25000
 w=load_weights();pts=points(a,b)
 start=time.perf_counter_ns()
 for _ in range(repeats):
  predictions=bytes(infer(x,y,w) for x,y in pts)
 ms=(time.perf_counter_ns()-start)/1e6
 digest=hashlib.sha256(predictions).hexdigest()
 assert digest==EXPECTED[(a,b)],"MODEL_OUTPUT_MISMATCH"
 return {"schema":SCHEMA,"start":a,"end":b,"cases":len(pts),"repetitions":repeats,
 "prediction_sha256":digest,"predictions_hex":predictions.hex(),"positive_count":sum(predictions),
 "compute_ms":round(ms,3),"model_npz_sha256":MODEL_SHA256,
 "packed_weights_sha256":WEIGHTS_SHA256,"runner_name":os.environ.get("RUNNER_NAME","local"),
 "platform":platform.platform()}
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--start",type=int,required=True)
 ap.add_argument("--end",type=int,required=True)
 ap.add_argument("--repetitions",type=int,default=20000)
 ap.add_argument("--output",required=True)
 args=ap.parse_args()
 res=run(args.start,args.end,args.repetitions)
 out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(res,sort_keys=True,indent=2)+"\n",encoding="utf-8")
 print("GENESIS_NEURAL_MESH_V05_RESULT "+json.dumps({k:v for k,v in res.items() if k!="predictions_hex"},sort_keys=True))
if __name__=="__main__":main()
