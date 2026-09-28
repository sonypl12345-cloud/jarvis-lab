#!/usr/bin/env python3
import json,os,time,urllib.request,subprocess,pathlib
TOKEN_FILE=os.path.expanduser('~/.genesis_github/token')
REPO='sonypl12345-cloud/jarvis-lab'; PR=2; DEVICE='oneplus10t-b40'
BASE=pathlib.Path.home()/ 'GenesisBridge40/github_transport'
STATE=BASE/'return_path_state_0_3.json'; AUDIT=BASE/'return_path_audit_0_3.jsonl'; API='https://api.github.com'
ALLOW={'process_inspect','process_restart'}
CANARY=BASE/'recovery_canary_0_2.py'; CANARY_PID=BASE/'recovery_canary.pid'

def token(): return open(TOKEN_FILE,encoding='utf-8').read().strip()
def req(method,path,body=None):
 data=None if body is None else json.dumps(body).encode()
 r=urllib.request.Request(API+path,data=data,method=method,headers={'Authorization':'Bearer '+token(),'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Genesis-Return-Path-0.3'})
 with urllib.request.urlopen(r,timeout=15) as x:return json.loads(x.read().decode())
def load():
 try:return json.load(open(STATE))
 except:return {'done':[]}
def save(s):
 BASE.mkdir(parents=True,exist_ok=True); tmp=str(STATE)+'.tmp'; open(tmp,'w').write(json.dumps(s)); os.replace(tmp,STATE)
def audit(event,**kw):
 BASE.mkdir(parents=True,exist_ok=True)
 row={'ts':int(time.time()),'event':event,**kw}
 with open(AUDIT,'a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
def parse(body):
 if not body.startswith('GENESIS_COMMAND\n'):return None
 a=body.find('```json\n'); b=body.find('\n```',a+8)
 if a<0 or b<0:return None
 try:return json.loads(body[a+8:b])
 except:return None
def alive(pid):
 try: os.kill(pid,0); return True
 except:return False
def inspect():
 out={'bridge_pid_file':None,'bridge_pid_alive':False,'canary_pid':None,'canary_alive':False,'time':int(time.time())}
 p=pathlib.Path.home()/'GenesisBridge40/bridge40.pid'
 try:
  pid=int(p.read_text().strip());out['bridge_pid_file']=pid;out['bridge_pid_alive']=alive(pid)
 except:pass
 try:
  cpid=int(CANARY_PID.read_text().strip());out['canary_pid']=cpid;out['canary_alive']=alive(cpid)
 except:pass
 return out
def restart_canary(service):
 if service!='genesis_recovery_canary': return {'ok':False,'reason':'BAD_SERVICE'}
 old=None
 try: old=int(CANARY_PID.read_text().strip())
 except: pass
 if old and alive(old):
  return {'ok':False,'reason':'ALREADY_ALIVE','service':service,'old_pid':old,'alive':True}
 p=subprocess.Popen(['python',str(CANARY)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
 time.sleep(1)
 ok=alive(p.pid)
 return {'ok':ok,'service':service,'old_pid':old,'new_pid':p.pid,'alive':ok}
def post(obj): req('POST',f'/repos/{REPO}/issues/{PR}/comments',{'body':'GENESIS_RESULT\n```json\n'+json.dumps(obj,indent=2)+'\n```'})
def once(dry=False):
 s=load();done=set(s.get('done',[]));comments=req('GET',f'/repos/{REPO}/issues/{PR}/comments?per_page=100');handled=0
 for c in comments:
  cmd=parse(c.get('body',''))
  if not cmd:continue
  cid=str(cmd.get('command_id',''))
  if not cid:continue
  if cid in done:
   audit('DUPLICATE_IGNORED',command_id=cid);continue
  if cmd.get('target')!=DEVICE:
   audit('WRONG_TARGET_IGNORED',command_id=cid,target=cmd.get('target'));continue
  now=int(time.time());exp=int(cmd.get('expires_at',0) or 0)
  if exp and now>exp:
   audit('EXPIRED_DENIED',command_id=cid,expires_at=exp,now=now)
   if not dry:post({'command_id':cid,'status':'DENIED','reason':'EXPIRED','device':DEVICE})
   done.add(cid);handled+=1;continue
  action=cmd.get('action')
  if action not in ALLOW:
   audit('NOT_ALLOWLISTED_DENIED',command_id=cid,action=action)
   if not dry:post({'command_id':cid,'status':'DENIED','reason':'NOT_ALLOWLISTED','device':DEVICE})
   done.add(cid);handled+=1;continue
  if action=='process_inspect': result=inspect(); verified=True; status='DONE'
  else:
   result=restart_canary((cmd.get('args') or {}).get('service'))
   if result.get('reason')=='ALREADY_ALIVE':
    verified=False; status='DENIED'; audit('ALREADY_ALIVE_DENIED',command_id=cid,pid=result.get('old_pid'))
   else:
    verified=bool(result.get('ok') and result.get('alive')); status='DONE' if verified else 'FAILED'
  if not dry:post({'command_id':cid,'status':status,'verified':verified,'device':DEVICE,'action':action,'result':result})
  done.add(cid);handled+=1
 if not dry:s['done']=list(done)[-500:];save(s)
 print(json.dumps({'verdict':'PASS','handled':handled,'dry_run':dry}))
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--dry-run',action='store_true');p.add_argument('--daemon',action='store_true');p.add_argument('--poll',type=int,default=10);a=p.parse_args()
 if a.daemon:
  while True:
   try:once(False)
   except Exception as e:
    audit('LOOP_ERROR',error=type(e).__name__);print(json.dumps({'verdict':'FAIL','error':type(e).__name__}),flush=True)
   time.sleep(max(5,a.poll))
 else:once(a.dry_run)
