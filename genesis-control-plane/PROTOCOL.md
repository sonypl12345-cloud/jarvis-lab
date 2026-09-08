# Genesis Control Plane Pilot

Goal: validate GitHub as a backup transport and as a wake-signal carrier for Genesis Bridge.

## Channels
- Primary transport: Supabase
- Backup transport: GitHub
- Wake candidate: GitHub pull-request activity -> ChatGPT Work event-trigger

## Safety
- Never store Supabase keys, GitHub tokens, bridge tokens, passwords, or private screenshots in the repository.
- Wake payloads contain only event IDs, type, priority, device alias, timestamps, hashes, and pointers to evidence stored elsewhere.
- Commands are idempotent and require command_id + expiry + expected postcondition.
- Bridge verifies results before ACK.

## Queue convention
- phone/events/<event_id>.json : phone -> cloud event envelope
- commands/<command_id>.json : cloud -> phone command envelope
- results/<command_id>.json : phone -> cloud verification/result envelope

## Pilot
The pilot branch is isolated from main. First test: GitHub write/read. Second test: phone -> GitHub. Third test: GitHub PR activity -> ChatGPT Work wake trigger.
