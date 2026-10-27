# GENESIS QUIESCENT ECO v0.1

A reversible Windows power profile for an always-reachable GENESIS laptop.

## Intended behavior
- AC power: display off after 2 minutes by default.
- AC power: Sleep disabled.
- AC power: Hibernate timeout disabled.
- Battery/DC settings: untouched.
- Existing GENESIS Remote companion/watchdog: not replaced or duplicated.
- Optional lid behavior is **not** changed unless `--lid-do-nothing` is explicitly supplied.
- No router credentials, cloud keys, or secrets are stored.

## Commands
```bat
python genesis_quiescent_eco.py status
python genesis_quiescent_eco.py install --monitor-minutes 2
python genesis_quiescent_eco.py enter
python genesis_quiescent_eco.py rollback
```

`install` saves the original AC power values before making changes and writes helper CMD files under:
`%LOCALAPPDATA%\GENESISNomad\quiescent_eco\`.

## Verification contract
After install:
1. `status` must show AC display timeout = 120 seconds, AC standby = 0, AC hibernate timeout = 0.
2. DC/battery values must match the pre-install backup.
3. GENESIS Remote companion port 8765 should be listening and the existing watchdog should remain registered.
4. `enter` should turn the display off without entering S3.
5. Remote control should remain reachable while the display is off.
6. `rollback` must restore exact backed-up AC values.

## Safety
This profile intentionally does **not** disable hibernation globally and does not change battery policy. It also leaves lid-close behavior unchanged by default to avoid thermal surprises on laptops whose cooling depends on an open lid.
