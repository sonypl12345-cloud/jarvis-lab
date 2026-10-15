#!/usr/bin/env python3
"""GENESIS Neural Mesh v0.2: isolated public, keyless CPU remote canary.
Portable 49 trained float32 parameters from v0.1 expert_0; no external imports.
Fixed deterministic inputs, no network, secrets, Android, or production access.
"""
import base64
import hashlib
import json
import math
import platform
import struct
import time

SCHEMA = "GENESIS_NEURAL_MESH_REMOTE_CANARY/0.2"
PARENT_NPZ_SHA256 = "f156378799b6a67ae8e6c754f00e302785fcc130fa914d4c830747655aaa7e00"
PACKED_SHA256 = "674a35040841dc2b7bb7e227327a78ffa4a3c9a03fd16d0fd24cebb5eadf1577"
PACKED = "DlMOwKDMiz17rA+9bwFKP2f1WL4D42s9/DQHQGLqiL0eCts+MZmrvb/+gD/por29OJslQLV0ir1t4Pm/ereQPcAzCsBEwYo9Kg5EPxrn3b18lRQ/hpqKPygwAsCne5E9iVZavMSSgT8gQVs/Kp4jPDVh/b6aNPO8BE6oPOBIvrtqkky88QmeveohSj+RgNm7IGfCv2lnDL1NE4i+rdXRP+lJkD5PyCg/bBfKP4or8b/JgsW/SVvlPohKpj/RoD3ADG8ZPg=="

def infer(x, y, w):
    h = [math.tanh(w[2*i] * x + w[2*i+1] * y + w[24+i]) for i in range(12)]
    z = sum(w[36+i] * h[i] for i in range(12)) + w[48]
    return int(z >= 0.0)

def main():
    raw = base64.b64decode(PACKED, validate=True)
    assert len(raw) == 196 and hashlib.sha256(raw).hexdigest() == PACKED_SHA256, "WEIGHTS_MISMATCH"
    weights = struct.unpack("<49f", raw)
    cases = []
    for i in range(256):
        h = hashlib.sha256(("genesis-neural-mesh-v02-case-" + str(i)).encode()).digest()
        a, b = struct.unpack("<HH", h[:4])
        cases.append((a * 4.0 / 65535.0 - 2.0, b * 4.0 / 65535.0 - 2.0))
    start = time.perf_counter_ns()
    for _ in range(200):
        predictions = [infer(x, y, weights) for x, y in cases]
    elapsed_ms = (time.perf_counter_ns() - start)/1e6
    result = {
        "schema": SCHEMA, "verified_weights": True,
        "parent_npz_sha256": PARENT_NPZ_SHA256,
        "packed_sha256": PACKED_SHA256,
        "cases": len(cases), "repetitions": 200,
        "inputs_sha256": hashlib.sha256(json.dumps(cases,separators=(",",":")).encode()).hexdigest(),
        "predictions_sha256": hashlib.sha256(bytes(predictions)).hexdigest(),
        "positive_count": sum(predictions),
        "elapsed_ms": round(elapsed_ms, 3),
        "runtime": platform.python_version(),
        "os": platform.system(),
    }
    print("GENESIS_NEURAL_MESH_V02_RESULT " + json.dumps(result,sort_keys=True,separators=(",",":")))

if __name__ == "__main__":
    main()
