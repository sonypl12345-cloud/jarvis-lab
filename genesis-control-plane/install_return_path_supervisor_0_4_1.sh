#!/data/data/com.termux/files/usr/bin/bash
set -u
D="$HOME/GenesisBridge40/github_transport"
SUP="$D/return_path_supervisor_0_4_1.py"
URL="https://raw.githubusercontent.com/sonypl12345-cloud/jarvis-lab/genesis/control-plane-pilot/genesis-control-plane/return_path_supervisor_0_4_1.py"

mkdir -p "$D"
echo "=== GENESIS RETURN PATH SUPERVISOR 0.4.1 INSTALL ==="

B="$(cat "$HOME/GenesisBridge40/bridge40.pid" 2>/dev/null || true)"
if [ -z "$B" ] || ! kill -0 "$B" 2>/dev/null; then
  echo "ABORT: Bridge worker unavailable"
  exit 1
fi
BCMD="$(tr '\0' ' ' < "/proc/$B/cmdline" 2>/dev/null || true)"
case "$BCMD" in
  *bridge40_worker.py*) echo "bridge ............ VERIFIED pid=$B" ;;
  *) echo "ABORT: bridge pid identity mismatch"; exit 1 ;;
esac

curl -fsSL "$URL" -o "$SUP" || { echo "ABORT: supervisor download failed"; exit 1; }
chmod 700 "$SUP"
python -m py_compile "$SUP" || { echo "ABORT: supervisor compile failed"; exit 1; }

echo "[✓] supervisor compile PASS"

OLD="$(cat "$D/return_path_supervisor.pid" 2>/dev/null || true)"
if [ -n "$OLD" ] && kill -0 "$OLD" 2>/dev/null; then
  OCMD="$(tr '\0' ' ' < "/proc/$OLD/cmdline" 2>/dev/null || true)"
  case "$OCMD" in
    *return_path_supervisor_0_4_1.py*) kill "$OLD"; sleep 1 ;;
  esac
fi

nohup python "$SUP" >> "$D/return_path_supervisor.stdout.log" 2>&1 &
NEW=$!
echo "$NEW" > "$D/return_path_supervisor.pid"
sleep 3

if ! kill -0 "$NEW" 2>/dev/null; then
  echo "FAIL: supervisor died"
  exit 1
fi

RP="$(cat "$D/return_path.pid" 2>/dev/null || true)"
if [ -n "$RP" ] && kill -0 "$RP" 2>/dev/null; then
  echo "return_path ......... ALIVE pid=$RP"
else
  echo "return_path ......... RECOVERY_PENDING"
fi

echo "supervisor .......... ALIVE pid=$NEW"
echo "bridge .............. ALIVE pid=$B"
echo "heartbeat ........... $D/return_path_supervisor.heartbeat.json"
echo "VERDICT ............. SUPERVISOR_INSTALLED_PASS"
