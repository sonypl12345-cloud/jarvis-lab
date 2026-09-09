#!/usr/bin/env python3
import json,os,time,urllib.request,subprocess,pathlib,argparse
TOKEN_FILE=os.path.expanduser('~/.genesis_github/token')
REPO='sonypl12345-cloud/jarvis-lab'; PR=2; DEVICE='oneplus10t-b40'
BASE=pathlib.Path.home()/'GenesisBridge40/github_transport'
STATE=BASE/'return_path_state_0_4.json'; AUDIT=BASE/'return_path_audit_0_4.jsonl'; API='https://api.github.com'
ALLOW={'process_inspect','process_restart'}
CANARY=BASE/'recovery_canary_0_2.py'; CANARY_PID=BASE/'recovery_canary.pid'
WINDOW=60; MAX_ATTEMPTS=3; COOLDOWN=120

def token(): return open(TOKEN_FILE,encoding='utf-8').read().strip()
def req(method,path,body=None):
 data=None if body is None else json.dumps(body).encode()
 r=urllib.request.Request(API+path,data=data,method=method,headers={'Authorization':'Bearer '+token(),'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Genesis-Return-Path-0.4'})
 with urllib.request.urlopen(r,timeout=15) as x:return json.loads(x.read().decode())
def load():
 try:return json.load(open(STATE))
 except:return {'done':[],'observed':[],'restart_attempts':[],'circuit_opened_at':None}
def save(s):
 BASE.mkdir(parents=True,exist_ok=True); tmp=str(STATE)+'.tmp'; open(tmp,'w').write(json.dumps(s)); os.replace(tmp,STATE)
def audit(event,**kw):
 BASE.mkdir(parents=True,exist_ok=True); row={'ts':int(time.time()),'event':event,**kw}
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
def prune_attempts(s,now):
 a=[int(x) for x in s.get('restart_attempts',[]) if now-int(x) <= WINDOW]; s['restart_attempts']=a; return a
def breaker_state(s,now):
 opened=s.get('circuit_opened_at')
 if opened is not None:
  if now-int(opened) < COOLDOWN:return 'OPEN'
  s['circuit_opened_at']=None; s['restart_attempts']=[]; audit('CIRCUIT_HALF_OPEN',cooldown=COOLDOWN); return 'HALF_OPEN'
 a=prune_attempts(s,now)
 return 'OPEN' if len(a)>=MAX_ATTEMPTS else 'CLOSED'
def restart_canary(service,s,now):
 if service!='genesis_recovery_canary': return {'ok':False,'reason':'BAD_SERVICE'},False
 old=None
 try: old=int(CANARY_PID.read_text().strip())
 except: pass
 if old and alive(old): return {'ok':False,'reason':'ALREADY_ALIVE','service':service,'old_pid':old,'alive':True},False
 state=breaker_state(s,now)
 if state=='OPEN':
  if s.get('circuit_opened_at') is None:s['circuit_opened_at']=now
  audit('CIRCUIT_OPEN_DENIED',service=service,attempts=len(s.get('restart_attempts',[])))
  return {'ok':False,'reason':'CIRCUIT_OPEN','service':service,'quarantined':True,'retry_after':max(0,COOLDOWN-(now-int(s['circuit_opened_at'])))},False
 s.setdefault('restart_attempts',[]).append(now)
 p=subprocess.Popen(['python',str(CANARY)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
 time.sleep(1); ok=alive(p.pid)
 if len(prune_attempts(s,int(time.time())))>=MAX_ATTEMPTS and not ok:
  s['circuit_opened_at']=int(time.time()); audit('QUARANTINED_AFTER_FAILURES',attempts=len(s['restart_attempts']))
 return {'ok':ok,'service':service,'old_pid':old,'new_pid':p.pid,'alive':ok,'breaker_state':breaker_state(s,int(time.time()))},True

def post(obj): req('POST',f'/repos/{REPO}/issues/{PR}/comments',{'body':'GENESIS_RESULT\n```json\n'+json.dumps(obj,indent=2)+'\n```'})
def once(dry=False):
 s=load();done=set(s.get('done',[]));observed=set(s.get('observed',[]));comments=req('GET',f'/repos/{REPO}/issues/{PR}/comments?per_page=100');handled=0
 for c in comments:
  cmd=parse(c.get('body',''))
  if not cmd:continue
  cid=str(cmd.get('command_id',''))
  if not cid:continue
  if cid in done:continue
  if cmd.get('target')!=DEVICE:
   if cid not in observed:audit('WRONG_TARGET_IGNORED',command_id=cid,target=cmd.get('target'));observed.add(cid)
   continue
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
  if action=='process_inspect':result=inspect();verified=True;status='DONE'
  else:
   result,attempted=restart_canary((cmd.get('args') or {}).get('service'),s,now);reason=result.get('reason')
   if reason in {'ALREADY_ALIVE','CIRCUIT_OPEN','BAD_SERVICE'}:verified=False;status='DENIED';audit(reason+'_DENIED',command_id=cid)
   else:verified=bool(result.get('ok') and result.get('alive'));status='DONE' if verified else 'FAILED'
  if not dry:post({'command_id':cid,'status':status,'verified':verified,'device':DEVICE,'action':action,'result':result})
  done.add(cid);handled+=1
 if not dry:
  s['done']=list(done)[-500:];s['observed']=list(observed)[-500:];save(s)
 print(json.dumps({'verdict':'PASS','handled':handled,'dry_run':dry,'breaker':breaker_state(s,int(time.time()))}))
def selftest():
 s={'done':[],'observed':[],'restart_attempts':[],'circuit_opened_at':None}; now=1000
 for i in range(3):s['restart_attempts'].append(now+i)
 assert breaker_state(s,1003)=='OPEN'; s['circuit_opened_at']=1003
 assert breaker_state(s,1050)=='OPEN'; assert breaker_state(s,1124)=='HALF_OPEN'; assert breaker_state(s,1124)=='CLOSED'
 print(json.dumps({'verdict':'PASS','test':'circuit_breaker','max_attempts':MAX_ATTEMPTS,'window':WINDOW,'cooldown':COOLDOWN}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--dry-run',action='store_true');p.add_argument('--daemon',action='store_true');p.add_argument('--poll',type=int,default=10);p.add_argument('--selftest',action='store_true');a=p.parse_args()
 if a.selftest:selftest()
 elif a.daemon:
  while True:
   try:once(False)
   except Exception as e:audit('LOOP_ERROR',error=type(e).__name__);print(json.dumps({'verdict':'FAIL','error':type(e).__name__}),flush=True)
   time.sleep(max(5,a.poll))
 else:once(a.dry_run)
