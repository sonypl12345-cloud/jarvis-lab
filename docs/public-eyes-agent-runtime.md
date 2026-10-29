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
