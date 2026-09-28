# GENESIS CLOSED LOOP 0.4.1 — STABLE CHECKPOINT

Status: REAL DEVICE PASS
Device: oneplus10t-b40
Date: 2026-09-09

## Proven behavior

- Phone → GitHub wake path: PASS.
- GitHub → Return Path command path: PASS.
- Return Path → phone execution → GitHub result path: PASS.
- process_inspect closed loop: PASS.
- recovery canary restart closed loop: PASS.
- TTL enforcement: expired command denied.
- wrong-target command: ignored, audited once, zero execution.
- duplicate handling: no second execution.
- restart semantics hardened to avoid duplicate canary process creation.
- PID reuse/stale pidfile handling: fixed in Return Path 0.4.1 using process identity checks.
- circuit breaker: 3 restart attempts in 60 seconds; subsequent recovery denied with circuit open/quarantine state; cooldown 120 seconds.
- real-device state evidence captured three restart timestamps followed by circuit_opened_at on the next attempt.
- Genesis Bridge worker remained alive after final real-device circuit test.

## Important defects found by red-team

1. Return Path 0.2 restart could create a second canary instead of replacing the prior instance.
2. Return Path 0.3 wrong-target audit repeated on every polling cycle.
3. PID-only liveness checks produced false ALREADY_ALIVE results after PID reuse/stale pidfiles.
4. Return Path itself can disappear under Android/Termux lifecycle conditions, motivating a dedicated supervisor.

## Safety boundaries

- No arbitrary shell execution in Return Path.
- process_restart target is limited to genesis_recovery_canary.
- Genesis Bridge is not an allowed restart target in this pilot.
- Commands are target checked, TTL checked and allowlisted.
- Circuit breaker limits repeated recovery activity.

## Stable components

- return_path_0_4_1.py
- recovery_canary_0_2.py
- return_path_supervisor_0_4_1.py
- install_return_path_0_4_1.sh
- install_return_path_supervisor_0_4_1.sh

## Productionization rule

Return Path 0.4.1 should be kept alive by the dedicated Return Path supervisor. The supervisor verifies the current Bridge worker identity, verifies Return Path process identity, runs compile + selftest before recovery, rate-limits Return Path restarts, and writes a local heartbeat. It does not restart or modify Genesis Bridge.
