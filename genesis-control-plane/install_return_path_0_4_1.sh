#!/data/data/com.termux/files/usr/bin/bash
set -u
D="$HOME/GenesisBridge40/github_transport"
F="$D/return_path_0_4_1.py"
OLDPIDFILE="$D/return_path.pid"
URL="https://raw.githubusercontent.com/sonypl12345-cloud/jarvis-lab/genesis/control-plane-pilot/genesis-control-plane/return_path_0_4_1.py"

echo "=== GENESIS RETURN PATH 0.4.1 SAFE INSTALL ==="

B="$(cat "$HOME/GenesisBridge40/bridge40.pid" 2>/dev/null || true)"
if [ -z "$B" ] || ! kill -0 "$B" 2>/dev/null; then
  echo "ABORT: Bridge worker unavailable"
  exit 1
fi
BCMD="$(tr '\0' ' ' < "/proc/$B/cmdline" 2>/dev/null || true)"
case "$BCMD" in
  *bridge40_worker.py*) echo "bridge ............ VERIFIED pid=$B" ;;
  *) echo "ABORT: bridge pidfile identity mismatch"; exit 1 ;;
esac

OLD="$(cat "$OLDPIDFILE" 2>/dev/null || true)"
if [ -n "$OLD" ] && kill -0 "$OLD" 2>/dev/null; then
  echo "old return path ... ALIVE pid=$OLD"
else
  echo "old return path ... NOT ALIVE"
fi

curl -fsSL "$URL" -o "$F" || { echo "ABORT: download failed"; exit 1; }
chmod 700 "$F"
python -m py_compile "$F" || { echo "ABORT: compile failed"; exit 1; }
python "$F" --selftest || { echo "ABORT: selftest failed"; exit 1; }
echo "[✓] compile + selftest PASS"

if [ -n "$OLD" ] && kill -0 "$OLD" 2>/dev/null; then
  kill "$OLD"
  sleep 1
fi

nohup python "$F" --daemon --poll 5 >> "$D/return_path_0_4_1.log" 2>&1 &
NEW=$!
echo "$NEW" > "$OLDPIDFILE"
sleep 3

if ! kill -0 "$NEW" 2>/dev/null; then
  echo "FAIL: Return Path 0.4.1 died"
  exit 1
fi
if ! kill -0 "$B" 2>/dev/null; then
  echo "FAIL: Bridge worker changed/dead"
  exit 1
fi

echo "return_path_0.4.1 ... ALIVE pid=$NEW"
echo "bridge .............. ALIVE pid=$B"
C="$(cat "$D/recovery_canary.pid" 2>/dev/null || true)"
echo "canary pidfile ....... ${C:-NONE}"
echo "VERDICT .............. INSTALLED_PASS"
