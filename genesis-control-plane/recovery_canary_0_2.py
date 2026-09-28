#!/usr/bin/env python3
import os,time,signal,pathlib
BASE=pathlib.Path.home()/"GenesisBridge40/github_transport"
PID=BASE/"recovery_canary.pid"
HB=BASE/"recovery_canary.heartbeat"
RUN_FOR=int(os.getenv("GENESIS_CANARY_RUN_FOR","0"))
start=time.time(); PID.write_text(str(os.getpid()))
try:
    while True:
        HB.write_text(str(time.time()))
        if RUN_FOR and time.time()-start>=RUN_FOR:
            break
        time.sleep(2)
finally:
    try: PID.unlink()
    except: pass
