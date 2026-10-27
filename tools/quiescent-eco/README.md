# GENESIS QUIESCENT ECO v0.2

A reversible Windows power profile for an always-reachable GENESIS laptop while preserving normal Windows display/media behavior.

## Intended behavior
- AC power: **preserve the existing Windows display timeout** by default.
- Active video/media can keep the display awake through normal Windows power requests, exactly like the standard Windows behavior.
- AC power: Sleep disabled.
- AC power: Hibernate timeout disabled.
- Battery/DC settings: untouched.
- Existing GENESIS Remote companion/watchdog: not replaced or duplicated.
- Optional lid behavior is **not** changed unless `--lid-do-nothing` is explicitly supplied.
- No router credentials, cloud keys, or secrets are stored.

## Commands
```bat
python genesis_quiescent_eco.py status
python genesis_quiescent_eco.py install
python genesis_quiescent_eco.py enter
python genesis_quiescent_eco.py rollback
```

Optional override if a custom display timeout is ever desired:
```bat
python genesis_quiescent_eco.py install --monitor-minutes 5
```

By default, `install` does **not** touch the display timeout. It only prevents automatic Sleep/Hibernate on AC power, so Windows keeps its standard idle/media logic.

`enter` is manual only: it immediately turns the display off. It is not used for normal automatic idle handling.

Before the first mutation, the installer stores a power-plan backup under:
`%LOCALAPPDATA%\GENESISNomad\quiescent_eco\power_backup.json`.

## Verification contract
After install:
1. AC display timeout must equal the pre-install value unless an explicit `--monitor-minutes` override was supplied.
2. AC standby timeout is 0.
3. AC hibernate timeout is 0.
4. DC/battery values match the pre-install backup.
5. GENESIS Remote companion port 8765 remains reachable and the existing watchdog stays registered.
6. `powercfg /requests` is surfaced in status so active media/display requests can be inspected.
7. `rollback` restores the exact backed-up AC values.

## Safety
This profile does not disable hibernation globally and does not change battery policy. It leaves lid-close behavior unchanged by default to avoid thermal surprises on laptops whose cooling depends on an open lid.
