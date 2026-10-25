from pathlib import Path
import importlib.util,json,socket,subprocess,sys,time,winreg

ROOT=Path(__file__).resolve().parent
SERVER=ROOT/"genesis_remote_server.py"
PORT=8765

def run(args,timeout=120):
    return subprocess.run(args,capture_output=True,text=True,timeout=timeout)

out={"schema":"GENESIS_REMOTE_INSTALL_V02","root":str(ROOT)}

needed=[]
if importlib.util.find_spec("PIL") is None:
    needed.append("Pillow")
if importlib.util.find_spec("cv2") is None:
    needed.append("opencv-python-headless")

if needed:
    p=run([sys.executable,"-m","pip","install","--user","--disable-pip-version-check",*needed],180)
    out["pip_rc"]=p.returncode
    out["pip_tail"]=(p.stdout+"\n"+p.stderr)[-2500:]
    if p.returncode:
        out.update(verdict="BLOCKED",reason="dependency_install_failed")
        print(json.dumps(out,ensure_ascii=False))
        raise SystemExit(3)

pythonw=Path(sys.executable).with_name("pythonw.exe")
exe=str(pythonw if pythonw.exists() else Path(sys.executable))
run_cmd=f'"{exe}" "{SERVER}"'

with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r"Software\Microsoft\Windows\CurrentVersion\Run",0,winreg.KEY_SET_VALUE) as k:
    winreg.SetValueEx(k,"GENESISRemote",0,winreg.REG_SZ,run_cmd)
out["autostart"]="HKCU_RUN"

def listening():
    try:
        with socket.create_connection(("127.0.0.1",PORT),timeout=.5):
            return True
    except OSError:
        return False

if not listening():
    flags=getattr(subprocess,"CREATE_NO_WINDOW",0)|getattr(subprocess,"DETACHED_PROCESS",0)
    subprocess.Popen([exe,str(SERVER)],cwd=str(ROOT),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
    for _ in range(24):
        if listening():
            break
        time.sleep(.25)

out["listening_local"]=listening()

fw=run(["netsh","advfirewall","firewall","add","rule","name=GENESIS Remote 8765","dir=in","action=allow","protocol=TCP","localport=8765","profile=private"],30)
out["firewall_rc"]=fw.returncode
out["firewall_tail"]=(fw.stdout+"\n"+fw.stderr)[-1200:]
out["port"]=PORT
out["verdict"]="PASS" if out["listening_local"] else "FAIL"

print(json.dumps(out,ensure_ascii=False))
raise SystemExit(0 if out["listening_local"] else 4)
