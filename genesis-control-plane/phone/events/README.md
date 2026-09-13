# Phone event queue

Each file is a minimal wake envelope. Do not commit secrets or sensitive evidence here.

Example:
```json
{
  "schema": "genesis.wake.v1",
  "event_id": "evt-example",
  "event_type": "TEMP_HIGH",
  "priority": "high",
  "device": "oneplus10t-b40",
  "created_at": "RFC3339 timestamp",
  "evidence_ref": "supabase:event-id-or-local-hash"
}
```
