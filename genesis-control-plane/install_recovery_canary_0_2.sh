#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
D="$HOME/GenesisBridge40/github_transport"
BASE="https://raw.githubusercontent.com/sonypl12345-cloud/jarvis-lab/genesis/control-plane-pilot/genesis-control-plane"
mkdir -p "$D"
for f in recovery_canary_0_2.py recovery_watchdog_0_2.py return_path_0_2.py; do
  curl -fsSL "$BASE/$f" -o "$D/$f"
  chmod 700 "$D/$f"
done
python -m py_compile "$D/recovery_canary_0_2.py" "$D/recovery_watchdog_0_2.py" "$D/return_path_0_2.py"
# Stop only the old GitHub return-path daemon if recorded.
if [ -s "$D/return_path.pid" ]; then
  OLD="$(cat "$D/return_path.pid" 2>/dev/null || true)"
  [ -n "$OLD" ] && kill "$OLD" 2>/dev/null || true
fi
rm -f "$D/recovery_watchdog_fired" "$D/recovery_canary.pid" "$D/recovery_canary.heartbeat"
nohup python "$D/return_path_0_2.py" --daemon --poll 5 >> "$D/return_path_0_2.log" 2>&1 &
echo $! > "$D/return_path.pid"
# Canary intentionally exits after 12 seconds; this is the controlled failure.
nohup env GENESIS_CANARY_RUN_FOR=12 python "$D/recovery_canary_0_2.py" >> "$D/recovery_canary.log" 2>&1 &
echo $! > "$D/recovery_canary_boot.pid"
# After the planned failure, watchdog emits one RECOVERY_CANARY_TEST event.
nohup sh -c "sleep 16; python '$D/recovery_watchdog_0_2.py' >> '$D/recovery_watchdog.log' 2>&1" >/dev/null 2>&1 &
echo "=== GENESIS CLOSED LOOP 0.2 BOOTSTRAP ==="
echo "return_path_pid ... $(cat "$D/return_path.pid")"
echo "canary_boot_pid ... $(cat "$D/recovery_canary_boot.pid")"
echo "canary_failure .... SCHEDULED +12s"
echo "watchdog_wake ..... SCHEDULED +16s"
echo "real_bridge ........ UNTOUCHED"
echo "VERDICT ............ ARMED"
