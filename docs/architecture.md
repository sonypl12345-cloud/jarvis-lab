# Architecture

```text
User goal
   ↓
Memory recall ──→ source + confidence
   ↓
Intent and permission gate
   ↓
Perception: DOM → UIA → OCR/Vision → coordinates as last resort
   ↓
Plan one bounded action
   ↓
Freshness and approval check
   ↓
Execute
   ↓
Verify expected state change
   ↓
Record outcome, lesson, and checkpoint
```

## Memory layers

- Working memory: the active request and current state.
- Episodic memory: compact facts, decisions, outcomes, and sources.
- Long-term policy: identity, values, safety boundaries, and tested procedures.

Raw logs are retained locally but are not loaded into every prompt. Retrieval
selects only relevant source-linked facts.

## Perception hierarchy

1. DOM for browser pages.
2. UI Automation for native Windows controls.
3. OCR and vision for unstructured surfaces.
4. Coordinates only when grounded and independently verified.

## Freshness

Every UI snapshot needs an ID, version, timestamp, TTL, invalidation reason,
and expected post-action state. Dynamic pages use shorter TTLs and mutation
signals. A stale snapshot cannot authorize an action.
