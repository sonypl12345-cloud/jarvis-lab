#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
D="$HOME/GenesisBridge40/github_transport"
T="$HOME/.genesis_github/token"
F="$D/return_path_0_4.py"
OLD_PID_FILE="$D/return_path.pid"
mkdir -p "$D"

echo "=== GENESIS RETURN PATH 0.4 SAFE INSTALL ==="
[ -s "$T" ] || { echo "ABORT: GitHub token missing"; exit 1; }
BRIDGE_PID="$(pgrep -f '/GenesisBridge40/bridge40_worker.py' | head -n1 || true)"
[ -n "$BRIDGE_PID" ] && kill -0 "$BRIDGE_PID" 2>/dev/null || { echo "ABORT: real Genesis Bridge not alive"; exit 1; }
OLD_RP="$(cat "$OLD_PID_FILE" 2>/dev/null || true)"
[ -n "$OLD_RP" ] && kill -0 "$OLD_RP" 2>/dev/null || { echo "ABORT: current Return Path not alive"; exit 1; }
echo "bridge ............ ALIVE pid=$BRIDGE_PID"
echo "old return path ... ALIVE pid=$OLD_RP"

curl -fsSL \
 -H "Authorization: Bearer $(cat "$T")" \
 -H "Accept: application/vnd.github.raw+json" \
 -H "X-GitHub-Api-Version: 2022-11-28" \
 "https://api.github.com/repos/sonypl12345-cloud/jarvis-lab/contents/genesis-control-plane/return_path_0_4.py?ref=genesis/control-plane-pilot" \
 -o "$F.new"
python -m py_compile "$F.new"
python "$F.new" --selftest
mv "$F.new" "$F"
chmod 700 "$F"
echo "[✓] compile + selftest PASS"

cp -p "$D/return_path_0_3.py" "$D/return_path_0_3.py.pre04" 2>/dev/null || true
kill "$OLD_RP"
sleep 1
nohup python "$F" --daemon --poll 5 >> "$D/return_path_0_4.log" 2>&1 &
NEW=$!
echo "$NEW" > "$OLD_PID_FILE"
sleep 3
if ! kill -0 "$NEW" 2>/dev/null; then
 echo "FAIL: 0.4 died; attempting rollback"
 if [ -f "$D/return_path_0_3.py" ]; then
  nohup python "$D/return_path_0_3.py" --daemon --poll 5 >> "$D/return_path_0_3.log" 2>&1 &
  RB=$!; echo "$RB" > "$OLD_PID_FILE"; echo "rollback_pid=$RB"
 fi
 exit 1
fi
kill -0 "$BRIDGE_PID" 2>/dev/null || { echo "FAIL: Bridge state changed"; exit 1; }
echo "return_path_0.4 ... ALIVE pid=$NEW"
echo "bridge ............ ALIVE pid=$BRIDGE_PID"
echo "canary ............ $(pgrep -f 'recovery_canary_0_2.py' | tr '\n' ' ' || true)"
echo "VERDICT ........... INSTALLED_PASS"
