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

## Work wake contract
On every supported `pull_request.ready_for_review` wake for PR #2:
1. Read this protocol before handling work.
2. Check the addressed GENESIS Live Bus inbox first for the current Work chat identity.
3. Preserve the message `correlation_id` and exact `reply_to` relationship.
4. ACK may acknowledge receipt, but ACK is not terminal when the addressed message declares `expected_event=RESULT`, `ack_is_terminal=false`, or `terminal_event=RESULT_OR_BLOCK`.
5. For an addressed `READ_ONLY_VERIFICATION` mission, execute the requested read-only verification using only authorized read-only connectors/tools. Do not modify Bridge, phone, repository files, database schema, grants, or data unless the mission explicitly and safely authorizes a separate mutation.
6. After execution, emit a Live Bus `RESULT` to the original sender with the same `correlation_id`, concise evidence, and `reply_to` pointing to the original mission message. If execution cannot be completed, emit `BLOCK` with the same `correlation_id` and a concrete reason.
7. Do not finish a wake run after ACK alone when a terminal RESULT/BLOCK is required.
8. Process at most one addressed test mission per wake during this pilot unless the protocol is explicitly revised.

## Pilot
The pilot branch is isolated from main. First test: GitHub write/read. Second test: phone -> GitHub. Third test: GitHub PR activity -> ChatGPT Work wake trigger.
