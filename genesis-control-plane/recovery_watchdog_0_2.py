#!/usr/bin/env python3
import json,os,time,urllib.request,pathlib
TOKEN_FILE=os.path.expanduser('~/.genesis_github/token'); REPO='sonypl12345-cloud/jarvis-lab'; PR=2; API='https://api.github.com'
BASE=pathlib.Path.home()/ 'GenesisBridge40/github_transport'; PID=BASE/'recovery_canary.pid'; FIRED=BASE/'recovery_watchdog_fired'
def token():return open(TOKEN_FILE).read().strip()
def req(method,path,body=None):
 data=None if body is None else json.dumps(body).encode();r=urllib.request.Request(API+path,data=data,method=method,headers={'Authorization':'Bearer '+token(),'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'Genesis-Recovery-Watchdog'})
 with urllib.request.urlopen(r,timeout=15) as x:return json.loads(x.read().decode())
def alive(pid):
 try:os.kill(pid,0);return True
 except:return False
def once():
 pid=None
 try:pid=int(PID.read_text().strip())
 except:pass
 if pid and alive(pid):
  print(json.dumps({'verdict':'PASS','canary_alive':True,'wake_sent':False}));return
 if FIRED.exists():
  print(json.dumps({'verdict':'PASS','canary_alive':False,'wake_sent':False,'reason':'already_fired'}));return
 event={'event_type':'RECOVERY_CANARY_TEST','source':'oneplus10t-b40','timestamp':int(time.time()),'priority':'TEST','requested_action':'RECOVER_CANARY','message':'Recovery canary is not alive'}
 body='GENESIS_WAKE_EVENT\n```json\n'+json.dumps(event,indent=2)+'\n```'
 c=req('POST',f'/repos/{REPO}/issues/{PR}/comments',{'body':body}); FIRED.write_text(str(c.get('id'))); print(json.dumps({'verdict':'PASS','canary_alive':False,'wake_sent':True,'comment_id':c.get('id')}))
if __name__=='__main__':once()
