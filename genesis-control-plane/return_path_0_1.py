#!/usr/bin/env python3
"""Genesis GitHub Return Path 0.1 — safe phone-side command poller.
Reads PR #2 conversation comments and accepts only GENESIS_COMMAND JSON envelopes.
Pilot allowlist: process_inspect only. No shell execution.
"""
import json, os, time, urllib.request

TOKEN_FILE=os.path.expanduser('~/.genesis_github/token')
REPO='sonypl12345-cloud/jarvis-lab'
PR=2
DEVICE='oneplus10t-b40'
STATE=os.path.expanduser('~/GenesisBridge40/github_transport/return_path_state.json')
API='https://api.github.com'
ALLOW={'process_inspect'}

def token():
    return open(TOKEN_FILE,encoding='utf-8').read().strip()

def req(method,path,body=None):
    data=None if body is None else json.dumps(body).encode()
    r=urllib.request.Request(API+path,data=data,method=method,headers={'Authorization':'Bearer '+token(),'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Genesis-Return-Path'})
    with urllib.request.urlopen(r,timeout=15) as x: return json.loads(x.read().decode())

def load_state():
    try: return json.load(open(STATE))
    except Exception: return {'done':[]}

def save_state(s):
    os.makedirs(os.path.dirname(STATE),exist_ok=True)
    tmp=STATE+'.tmp'; open(tmp,'w').write(json.dumps(s)); os.replace(tmp,STATE)

def parse(body):
    if not body.startswith('GENESIS_COMMAND\n'): return None
    a=body.find('```json\n'); b=body.find('\n```',a+8)
    if a<0 or b<0: return None
    try: return json.loads(body[a+8:b])
    except Exception: return None

def inspect():
    # Read-only local evidence; no arbitrary command execution.
    out={'bridge_pid_file':None,'bridge_pid_alive':False,'time':int(time.time())}
    p=os.path.expanduser('~/GenesisBridge40/bridge40.pid')
    try:
        pid=int(open(p).read().strip()); out['bridge_pid_file']=pid
        os.kill(pid,0); out['bridge_pid_alive']=True
    except Exception: pass
    return out

def post(obj):
    req('POST',f'/repos/{REPO}/issues/{PR}/comments',{'body':'GENESIS_RESULT\n```json\n'+json.dumps(obj,indent=2)+'\n```'})

def once(dry=False):
    s=load_state(); done=set(s.get('done',[]))
    comments=req('GET',f'/repos/{REPO}/issues/{PR}/comments?per_page=100')
    handled=0
    for c in comments:
        cmd=parse(c.get('body',''))
        if not cmd: continue
        cid=str(cmd.get('command_id',''))
        if not cid or cid in done: continue
        if cmd.get('target')!=DEVICE: continue
        now=int(time.time()); exp=int(cmd.get('expires_at',0) or 0)
        if exp and now>exp:
            if not dry: post({'command_id':cid,'status':'DENIED','reason':'EXPIRED','device':DEVICE})
            done.add(cid); handled+=1; continue
        action=cmd.get('action')
        if action not in ALLOW:
            if not dry: post({'command_id':cid,'status':'DENIED','reason':'NOT_ALLOWLISTED','device':DEVICE})
            done.add(cid); handled+=1; continue
        result=inspect()
        if not dry: post({'command_id':cid,'status':'DONE','verified':True,'device':DEVICE,'action':action,'result':result})
        done.add(cid); handled+=1
    if not dry:
        s['done']=list(done)[-500:]; save_state(s)
    print(json.dumps({'verdict':'PASS','handled':handled,'dry_run':dry}))

def main():
    import argparse
    p=argparse.ArgumentParser(); p.add_argument('--once',action='store_true'); p.add_argument('--dry-run',action='store_true'); p.add_argument('--daemon',action='store_true'); p.add_argument('--poll',type=int,default=10); a=p.parse_args()
    if a.daemon:
        while True:
            try: once(False)
            except Exception as e: print(json.dumps({'verdict':'FAIL','error':type(e).__name__}),flush=True)
            time.sleep(max(5,a.poll))
    else: once(a.dry_run)
if __name__=='__main__': main()
