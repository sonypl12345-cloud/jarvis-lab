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
- RESEARCH_VERIFICATION missions are read-only with respect to Bridge, phone, production database state, grants, and repository code. They may read public web sources and authorized read-only project context.

## Queue convention
- phone/events/<event_id>.json : phone -> cloud event envelope
- commands/<command_id>.json : cloud -> phone command envelope
- results/<command_id>.json : phone -> cloud verification/result envelope
- `public.genesis_tasks` may hold durable research mission intent; Live Bus remains the ephemeral wake/coordination envelope.

## Work wake contract
On every supported `pull_request.ready_for_review` wake for PR #2:
1. Read this protocol before handling work.
2. Check the addressed GENESIS Live Bus inbox first for the current Work chat identity.
3. Preserve every message `correlation_id` and exact `reply_to` relationship.
4. ACK may acknowledge receipt, but ACK is not terminal when the addressed message declares `expected_event=RESULT`, `ack_is_terminal=false`, or `terminal_event=RESULT_OR_BLOCK`.
5. For an addressed `READ_ONLY_VERIFICATION` mission, execute the requested read-only verification using only authorized read-only connectors/tools. Do not modify Bridge, phone, repository files, database schema, grants, or data unless the mission explicitly and safely authorizes a separate mutation.
6. For an addressed `RESEARCH_VERIFICATION` dispatcher mission, process at most 3 embedded sub-missions in the payload. Keep evidence tracks separate. Use public web research and authorized read-only project context only. Do not modify Bridge, phone, production runtime, database schema/grants, or project truth state.
7. For each embedded research sub-mission, return a separate Live Bus `RESULT` or `BLOCK` to the original sender using that sub-mission's exact `correlation_id`. Include concise source trail/evidence and the dispatcher message id as `reply_to` when no more specific original message id is provided.
8. Do not finish a wake run after ACK alone when terminal RESULT/BLOCK is required.
9. A bounded dispatcher wake may process up to 3 embedded research sub-missions; other addressed missions remain one-per-wake during this pilot.

## Pilot
The pilot branch is isolated from main. First test: GitHub write/read. Second test: phone -> GitHub. Third test: GitHub PR activity -> ChatGPT Work wake trigger. Fourth test: bounded Live Bus research dispatcher -> wake -> RESULT/BLOCK.
