# GENESIS Public Eyes — agent runtime

Status: LAB canonical on `lab/camera-ahead-v01`.

## Purpose

Public Eyes is the perception registry used by JARVIS for requests such as:

- "де я?"
- "що є біля мене?"
- "які камери поруч?"
- "що попереду?"

It is an **agent-facing** capability, not a user-facing map.

## Battery-safe owner context

The owner position is obtained only on demand.

1. `genesis_internal.jarvis_eyes_start_v01(mode)` checks registry freshness and owner-location TTL.
2. If owner location is stale, `owner_location_start_v01(true)` verifies the OnePlus Bridge heartbeat.
3. If Bridge heartbeat is older than 45 s, GPS is not started.
4. Otherwise the request is submitted through canonical `bridge40_submit_command`.
5. The device executes the bounded ECO location snapshot script.
6. If Android Location was OFF, the script enables it temporarily, takes one location sample, restores the original state, and verifies the restore.
7. Only the singleton `owner-current` state is overwritten. No route history is retained.

## Registry architecture

Canonical private table:

`genesis_internal.public_eye_registry_v01`

Current metadata snapshot after 2026-10-29 expansion:

- total rows: 5,414
- auto-select candidates: 5,097
- vision-capable metadata rows: 5,230
- database footprint including indexes: about 3.3 MB
- raw JPEG/HLS/MP4 persistence: forbidden

Sources currently imported:

### WebCamera.pl

GitHub metadata registry:

`data/public_eyes/webcamera_registry.json`

Current source snapshot: 447 active coordinate-bearing entries.

The agent promotes outdoor, non-premium candidates. Frames are retrieved on demand from a fixed allowlisted host only.

### ARGOS public index window

GitHub metadata registry:

`data/public_eyes/argos_central_europe_registry.json`

Current source snapshot: 4,953 Central-Europe entries, including traffic, urban and environmental cameras.

Only fixed-format public-image endpoints are promoted:

`https://argosatlas.com/api/cam/<18-hex-id>/image`

Religious/indoor-looking candidates are excluded from automatic selection by name filters.

### Existing explicit Poznań sources

The existing manually verified sources such as MTP, UEP/UMWW Panorama Poznania and the strict Stary Rynek live source remain available. The imported WebCamera Stary Rynek entry is marked LIVE_VERIFIED based on the earlier independent HLS-live proof.

## Health gating

Registry presence never means "live".

Canonical flow:

`registry -> geometry -> bounded health probe -> best healthy eye -> ephemeral frame -> Vision`

Private probe:

`genesis_internal.public_eye_probe_v01(eye_id)`

Allowed providers are strictly host/pattern allowlisted:

- WebCamera preview JPEGs
- ARGOS public image endpoint

No arbitrary URL is accepted.

`best_public_eye_for_owner_v01(...)` checks only a small nearest shortlist, reuses a recent health probe when valid, and otherwise performs bounded HEAD probes. Thousands of registry rows therefore do **not** cause thousands of network requests per user query.

## Camera Broker v14

Edge Function:

`genesis-camera-broker-lab-v01`

New generic actions:

- `public_eye_probe`
- `public_eye_frame`
- `vision_input` for `webcamera:*` and `argos:*`

The Broker constructs the public URL from the validated eye ID. It never accepts an arbitrary URL for these actions.

Frame invariant:

- max 2 MB
- image/JPEG verification
- source freshness contract required
- `Cache-Control: no-store`
- `x-genesis-persistence: ephemeral-no-store`
- no Supabase Storage upload
- no database blob/base64 copy

The stricter HLS-proven Stary Rynek path remains available separately.

## Registry refresh

The GitHub LAB workflow `Public Eyes Registry LAB` refreshes metadata.

The private runtime also provides:

- `refresh_webcamera_registry_v01()`
- `refresh_argos_registry_v01()`
- `ensure_public_eye_registry_fresh_v01(interval '30 hours')`

Normal JARVIS calls only check the sync timestamp. No large metadata download occurs while the cached registry is fresh. If a refresh fails, the last known registry remains usable.

## Selection modes

`jarvis_eyes_start_v01('nearby')`

Returns nearest eyes by literal geographic distance plus a separately health-gated `best_healthy_eye`.

`jarvis_eyes_start_v01('ahead')`

Uses fresh/recent verified heading and a bounded forward cone.

A low-speed reused heading is explicitly labelled rather than presented as a fresh movement bearing.

## Public-road expansion candidates

The official Września traffic page publishes four entry-road camera views (Daszyńskiego roundabout, Paderewskiego viaduct, Wrocławska from Miłosław, Wrocławska/Działkowców). They remain discovery candidates until precise camera geometry and a currently healthy media transport are independently verified.

GDDKiA's official road-information map explicitly provides road-camera imagery. Its current camera-layer transport is not promoted because the public browser layer has not yet yielded a stable callable metadata endpoint in our headless LAB. No credential/cookie bypass is permitted.

## Privacy and safety

Public intentionally published cameras only.

No private feeds, credential replay, access-control bypass, public face tracking, identity search, raw bystander-footage archive, or owner route history.


## Local coverage policy (0–2 km)

For requests meaning “right near me”, JARVIS must not present a healthy but distant city camera as if it were local.

Canonical threshold:

- target local-public radius: 2,000 m;
- `genesis_internal.local_public_coverage_v01(2000)` reports whether a useful auto-select public Vision eye exists inside that radius;
- when no such eye exists, `coverage_gap=true`;
- a farther public camera remains a fallback only, not the primary “near me” answer.

Current Poznań south/west LAB finding on 2026-10-29: physical municipal/ZDM cameras exist around Górczyn/Hetmańska, but their streams are not generally public; the historical public Hetmańska/Głogowska and ZDM Górczyn images are currently unavailable. Do not bypass non-public monitoring.

## Owner rear eye — 0 m fallback

The preferred local-gap fallback is the owner-authorized OnePlus rear camera, one-shot only.

Verified LAB probe on `oneplus10t-b40`:

- `termux-camera-info`: PASS;
- 4 camera IDs visible to Termux API;
- rear camera `id=0`: PASS;
- one JPEG captured successfully;
- test frame size: 2,827,758 bytes;
- JPEG signature verified;
- test frame deleted in the same process;
- no raw frame persisted to Supabase or GitHub.

Target chain:

`user intent -> one-shot rear camera -> local VLM -> text-only scene summary -> delete JPEG -> JARVIS response`

Privacy contract:

- no continuous video;
- no face identification;
- people remain anonymous;
- no raw camera upload to Supabase Storage/database;
- no raw camera attachment is required for the agent path;
- camera runs only for an explicit context such as “look what is near me / ahead of me”.

## Local VLM LAB

The phone already has a multimodal-capable `llama.cpp` build with `llama-mtmd-cli`.

Selected model: `ggml-org/SmolVLM-500M-Instruct-GGUF`, Q8_0 plus Q8_0 multimodal projector.

Fixed integrity contract:

- model: 436,806,912 bytes, SHA-256 `9d4612de6a42214499e301494a3ecc2be0abdd9de44e663bda63f1152fad1bf4`;
- projector: 108,783,360 bytes, SHA-256 `d1eb8b6b23979205fdf63703ed10f788131a3f812c7b1f72e0119d5d81295150`.

Installer policy:

- LAB only;
- fixed URLs and hashes, no arbitrary download target;
- Wi-Fi only;
- battery/space guard;
- resumable `.part`;
- SHA-256 before atomic rename;
- no local inference while installation is incomplete.

The local Vision runner is one-shot and guarded: rear-camera temp JPEG -> optional resize -> `llama-mtmd-cli` -> short navigation-oriented anonymous scene description -> temp deletion in `finally`.

Do not mark Local VLM READY until both model files are fully verified and one real camera->description->delete test passes.
