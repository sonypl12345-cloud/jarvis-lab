#!/usr/bin/env python3
from __future__ import annotations
import argparse, ctypes, json, os, re, shutil, socket, subprocess, sys, time
from pathlib import Path

APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "GENESISNomad" / "quiescent_eco"
BACKUP_FILE = APP_DIR / "power_backup.json"
INSTALLED_SCRIPT = APP_DIR / "genesis_quiescent_eco.py"
VERSION = "0.3.0"
SETTINGS = {
    "display": ("SUB_VIDEO", "VIDEOIDLE"),
    "sleep": ("SUB_SLEEP", "STANDBYIDLE"),
    "hibernate": ("SUB_SLEEP", "HIBERNATEIDLE"),
    "lid": ("SUB_BUTTONS", "LIDACTION"),
}

def run(cmd, timeout=20):
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
    return {"rc":p.returncode,"out":p.stdout,"err":p.stderr}

def powercfg(*args): return run(["powercfg",*args])

def parse_indices(text):
    ac=re.search(r"Current AC Power Setting Index:\s*0x([0-9a-fA-F]+)",text)
    dc=re.search(r"Current DC Power Setting Index:\s*0x([0-9a-fA-F]+)",text)
    return (int(ac.group(1),16) if ac else None,int(dc.group(1),16) if dc else None)

def read_setting(subgroup,setting):
    r=powercfg("/q","SCHEME_CURRENT",subgroup,setting)
    ac,dc=parse_indices(r["out"])
    return {"rc":r["rc"],"ac":ac,"dc":dc,"err":r["err"][-1000:]}

def active_scheme():
    r=powercfg("/getactivescheme")
    m=re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F-]{27,})",r["out"])
    return m.group(1) if m else None

def power_requests():
    r=powercfg("/requests")
    return {"rc":r["rc"],"out":r["out"][-6000:],"err":r["err"][-1000:]}

def snapshot():
    return {"version":VERSION,"ts":time.time(),"active_scheme":active_scheme(),
            "settings":{n:read_setting(*s) for n,s in SETTINGS.items()},
            "power_requests":power_requests()}

def save_backup(force=False):
    APP_DIR.mkdir(parents=True,exist_ok=True)
    if BACKUP_FILE.exists() and not force:
        return json.loads(BACKUP_FILE.read_text(encoding="utf-8"))
    data=snapshot()
    BACKUP_FILE.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    return data

def set_ac(subgroup,setting,value):
    return powercfg("/setacvalueindex","SCHEME_CURRENT",subgroup,setting,str(value))

def activate(): return powercfg("/setactive","SCHEME_CURRENT")

def companion_status():
    port=False
    try:
        with socket.create_connection(("127.0.0.1",8765),timeout=0.5): port=True
    except OSError: pass
    watchdog=None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
            try: watchdog,_=winreg.QueryValueEx(k,"GENESISRemoteWatchdog")
            except FileNotFoundError: pass
    except Exception: pass
    return {"port_8765_listening":port,"watchdog_registered":bool(watchdog)}

def apply_profile(monitor_minutes=None,lid_do_nothing=False):
    backup=save_backup(False)
    results={}
    if monitor_minutes is not None:
        results["display"]=set_ac(*SETTINGS["display"],max(1,monitor_minutes)*60)
    results["sleep"]=set_ac(*SETTINGS["sleep"],0)
    results["hibernate"]=set_ac(*SETTINGS["hibernate"],0)
    if lid_do_nothing: results["lid"]=set_ac(*SETTINGS["lid"],0)
    results["activate"]=activate()
    ok=all(x["rc"]==0 for x in results.values())
    return {
        "schema":"GENESIS_QUIESCENT_ECO_APPLY_V02",
        "verdict":"PASS" if ok else "PARTIAL",
        "display_policy":"PRESERVE_WINDOWS_STANDARD" if monitor_minutes is None else f"SET_{max(1,monitor_minutes)}_MINUTES",
        "display_ac_before":backup.get("settings",{}).get("display",{}).get("ac"),
        "sleep_ac":"NEVER",
        "hibernate_ac":"NEVER",
        "battery_settings_changed":False,
        "lid_changed":lid_do_nothing,
        "results":{k:{"rc":v["rc"],"err":v["err"][-500:]} for k,v in results.items()},
        "backup_file":str(BACKUP_FILE),
        "companion":companion_status(),
        "post":snapshot()
    }

def rollback():
    if not BACKUP_FILE.exists():
        return {"schema":"GENESIS_QUIESCENT_ECO_ROLLBACK_V02","verdict":"BLOCKED","reason":"backup_missing"}
    b=json.loads(BACKUP_FILE.read_text(encoding="utf-8"))
    results={}
    for name,(sub,setting) in SETTINGS.items():
        ac=b.get("settings",{}).get(name,{}).get("ac")
        if ac is not None: results[name]=set_ac(sub,setting,int(ac))
    results["activate"]=activate()
    ok=all(x["rc"]==0 for x in results.values())
    return {"schema":"GENESIS_QUIESCENT_ECO_ROLLBACK_V02","verdict":"PASS" if ok else "PARTIAL",
            "results":{k:{"rc":v["rc"],"err":v["err"][-500:]} for k,v in results.items()},"post":snapshot()}

def pause_playing_media():
    try:
        import asyncio
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as MediaManager,
            GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
        )
    except Exception as e:
        return {"verdict":"UNAVAILABLE","error":type(e).__name__+":"+str(e)[:200],"sessions_seen":0,"paused":[]}

    async def _run():
        out={"verdict":"PASS","sessions_seen":0,"playing_seen":0,"paused":[],"failed":[]}
        try:
            mgr=await MediaManager.request_async()
            sessions=list(mgr.get_sessions())
            out["sessions_seen"]=len(sessions)
            for session in sessions:
                try:
                    info=session.get_playback_info()
                    source=session.source_app_user_model_id
                    if info.playback_status==PlaybackStatus.PLAYING:
                        out["playing_seen"]+=1
                        if bool(info.controls.is_pause_enabled):
                            ok=bool(await session.try_pause_async())
                            (out["paused"] if ok else out["failed"]).append(source)
                        else:
                            out["failed"].append(source+":pause_disabled")
                except Exception as e:
                    out["failed"].append(type(e).__name__+":"+str(e)[:120])
            if out["failed"] and not out["paused"]:
                out["verdict"]="PARTIAL"
            return out
        except Exception as e:
            return {"verdict":"FAIL","error":type(e).__name__+":"+str(e)[:240],"sessions_seen":0,"paused":[]}

    try:
        return asyncio.run(_run())
    except Exception as e:
        return {"verdict":"FAIL","error":type(e).__name__+":"+str(e)[:240],"sessions_seen":0,"paused":[]}

def screen_off():
    try:
        rc=ctypes.windll.user32.SendMessageW(0xFFFF,0x0112,0xF170,2)
        return {"ok":True,"return":int(rc)}
    except Exception as e:
        return {"ok":False,"error":type(e).__name__+":"+str(e)}

def enter_quiescent():
    media=pause_playing_media()
    time.sleep(0.25)
    s=screen_off()
    verdict="PASS" if s.get("ok") and media.get("verdict") in ("PASS","UNAVAILABLE") else "PARTIAL"
    return {"schema":"GENESIS_QUIESCENT_ECO_ENTER_V03","verdict":verdict,
            "media_pause":media,"screen_off":s,"companion":companion_status(),
            "note":"Pauses only sessions that are actually PLAYING, then turns the display off. It never auto-resumes media."}

def status():
    return {"schema":"GENESIS_QUIESCENT_ECO_STATUS_V02","version":VERSION,
            "power":snapshot(),"backup_exists":BACKUP_FILE.exists(),"companion":companion_status()}

def install(monitor_minutes=None,lid_do_nothing=False):
    APP_DIR.mkdir(parents=True,exist_ok=True)
    source=Path(__file__).resolve()
    if source != INSTALLED_SCRIPT.resolve(): shutil.copy2(source,INSTALLED_SCRIPT)
    pyexe=sys.executable
    helpers={
      "ENTER_QUIESCENT.cmd":f'@echo off\r\n"{pyexe}" "{INSTALLED_SCRIPT}" enter\r\n',
      "STATUS.cmd":f'@echo off\r\n"{pyexe}" "{INSTALLED_SCRIPT}" status\r\npause\r\n',
      "ROLLBACK.cmd":f'@echo off\r\n"{pyexe}" "{INSTALLED_SCRIPT}" rollback\r\npause\r\n'
    }
    for name,content in helpers.items(): (APP_DIR/name).write_text(content,encoding="utf-8")
    applied=apply_profile(monitor_minutes,lid_do_nothing)
    return {"schema":"GENESIS_QUIESCENT_ECO_INSTALL_V02","verdict":applied["verdict"],
            "installed_script":str(INSTALLED_SCRIPT),"helpers":[str(APP_DIR/x) for x in helpers],"apply":applied}

def main():
    ap=argparse.ArgumentParser(description="GENESIS QUIESCENT ECO for Windows")
    sub=ap.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("apply"); a.add_argument("--monitor-minutes",type=int,default=None); a.add_argument("--lid-do-nothing",action="store_true")
    i=sub.add_parser("install"); i.add_argument("--monitor-minutes",type=int,default=None); i.add_argument("--lid-do-nothing",action="store_true")
    sub.add_parser("enter"); sub.add_parser("status"); sub.add_parser("rollback")
    args=ap.parse_args()
    if args.cmd=="apply": out=apply_profile(args.monitor_minutes,args.lid_do_nothing)
    elif args.cmd=="install": out=install(args.monitor_minutes,args.lid_do_nothing)
    elif args.cmd=="enter": out=enter_quiescent()
    elif args.cmd=="status": out=status()
    else: out=rollback()
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
