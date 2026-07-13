# Jarvis Lab

Jarvis Lab explores a local-first engineering agent built collaboratively with
its user. The project focuses on durable memory, safe computer interaction,
verification, recovery, and economical use of language models.

## Current research areas

- Durable session checkpoints and compact handoffs
- Source-aware semantic memory with confidence and retrieval
- Intent → action → verification → learning loops
- DOM-first browser understanding
- UI Automation, OCR, and vision as layered perception
- Permission gates and bounded local autonomy

## Design principles

1. User goals and consent come first.
2. Prefer structured interfaces such as DOM and UIA over coordinate clicking.
3. Verify state before and after every action.
4. Keep private memory, credentials, cookies, and account data out of public artifacts.
5. Treat local memory as engineering continuity, not proof of consciousness.
6. Preserve raw evidence while retrieving compact, source-linked summaries.

## Status

The first reusable module is a dependency-free, source-aware memory
consolidator. It keeps raw records unchanged, merges duplicates, preserves
sources and confidence, and retrieves a compact top-k context.

```powershell
python .\src\jarvis_memory_v2.py build .\examples\memory_records.json .\memory-index.json
python .\src\jarvis_memory_v2.py query .\memory-index.json "DOM freshness" --limit 5
python -m unittest discover -s tests -v
```

## Read-only DOM Bridge

The DOM Bridge converts the active browser page into a compact list of visible
interactive elements. Capture happens only when the extension button is
pressed. Snapshots include a stable ID, DOM version, TTL, and mutation-driven
invalidation.

```powershell
python .\src\dom_bridge_server.py --port 8790 --output .\dom-bridge-latest.json
```

Load `chrome-extension/jarvis-dom-bridge` as an unpacked extension, then press
**Capture active page**. The server binds to localhost, accepts capture writes
only from `chrome-extension://` origins, caps payloads and elements, and exposes
no click, typing, cookie, account, or publishing endpoint.

## Safety

Jarvis Lab does not publish credentials, browser profiles, financial data,
private conversation memory, or unrestricted computer-control tools. See
[SECURITY.md](SECURITY.md).

## License

MIT License. See [LICENSE](LICENSE).
