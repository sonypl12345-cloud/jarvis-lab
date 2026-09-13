#!/usr/bin/env python3
import json, os, pathlib, subprocess, time

BASE = pathlib.Path.home() / 'GenesisBridge40/github_transport'
TARGET = BASE / 'return_path_0_4_1.py'
PIDFILE = BASE / 'return_path.pid'
SUP_PIDFILE = BASE / 'return_path_supervisor.pid'
HEARTBEAT = BASE / 'return_path_supervisor.heartbeat.json'
LOG = BASE / 'return_path_supervisor.log'
RP_LOG = BASE / 'return_path_0_4_1.log'
CHECK_INTERVAL = 10
WINDOW = 600
MAX_RESTARTS = 5
restart_times = []

def now():
    return int(time.time())

def proc_cmd(pid):
    try:
        return pathlib.Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0', b' ').decode(errors='ignore')
    except Exception:
        return ''

def alive_identity(pid, needle):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except Exception:
        return False
    return needle in proc_cmd(pid)

def read_pid(path):
    try:
        return int(path.read_text().strip())
    except Exception:
        return None

def write_atomic(path, text):
    tmp = pathlib.Path(str(path) + '.tmp')
    tmp.write_text(text)
    os.replace(tmp, path)

def log(event, **kw):
    row = {'ts': now(), 'event': event, **kw}
    with LOG.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')

def bridge_ok():
    p = pathlib.Path.home() / 'GenesisBridge40/bridge40.pid'
    pid = read_pid(p)
    return pid, alive_identity(pid, 'bridge40_worker.py')

def validate_target():
    if not TARGET.exists():
        return False, 'TARGET_MISSING'
    c = subprocess.run(['python', '-m', 'py_compile', str(TARGET)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if c.returncode != 0:
        return False, 'COMPILE_FAIL'
    t = subprocess.run(['python', str(TARGET), '--selftest'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if t.returncode != 0:
        return False, 'SELFTEST_FAIL'
    return True, 'PASS'

def start_return_path():
    global restart_times
    t = now()
    restart_times = [x for x in restart_times if t - x <= WINDOW]
    if len(restart_times) >= MAX_RESTARTS:
        log('RESTART_RATE_LIMIT', restarts=len(restart_times), window=WINDOW)
        return None, 'RATE_LIMIT'
    ok, reason = validate_target()
    if not ok:
        log('TARGET_VALIDATION_FAIL', reason=reason)
        return None, reason
    f = RP_LOG.open('ab', buffering=0)
    p = subprocess.Popen(['python', str(TARGET), '--daemon', '--poll', '5'], stdout=f, stderr=f, start_new_session=True)
    time.sleep(2)
    if not alive_identity(p.pid, 'return_path_0_4_1.py'):
        log('START_FAIL', pid=p.pid)
        return None, 'START_FAIL'
    write_atomic(PIDFILE, str(p.pid))
    restart_times.append(t)
    log('RETURN_PATH_STARTED', pid=p.pid)
    return p.pid, 'PASS'

def heartbeat(status, rp_pid=None, bridge_pid=None, detail=None):
    row = {'ts': now(), 'status': status, 'return_path_pid': rp_pid, 'bridge_pid': bridge_pid, 'detail': detail}
    write_atomic(HEARTBEAT, json.dumps(row))

def main():
    BASE.mkdir(parents=True, exist_ok=True)
    write_atomic(SUP_PIDFILE, str(os.getpid()))
    log('SUPERVISOR_START', pid=os.getpid())
    while True:
        bridge_pid, bok = bridge_ok()
        rp_pid = read_pid(PIDFILE)
        rok = alive_identity(rp_pid, 'return_path_0_4_1.py')
        if not bok:
            heartbeat('DEGRADED', rp_pid, bridge_pid, 'BRIDGE_UNAVAILABLE')
            log('BRIDGE_UNAVAILABLE', bridge_pid=bridge_pid)
        elif rok:
            heartbeat('ONLINE', rp_pid, bridge_pid, 'RETURN_PATH_OK')
        else:
            heartbeat('RECOVERING', rp_pid, bridge_pid, 'RETURN_PATH_DOWN')
            new_pid, reason = start_return_path()
            if new_pid:
                heartbeat('ONLINE', new_pid, bridge_pid, 'RETURN_PATH_RECOVERED')
            else:
                heartbeat('DEGRADED', rp_pid, bridge_pid, reason)
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main()
