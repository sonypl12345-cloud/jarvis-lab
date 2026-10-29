# Camera Ahead LAB v0.1

Goal: answer the owner's question **"what is ahead?"** by selecting legally
public road cameras in the direction of travel and presenting fresh visual
evidence to the existing Jarvis/GENESIS perception stack.

## Reuse, do not duplicate

The current private Live Map already owns:
- the owner's GPS position;
- movement state;
- weather;
- participant presence;
- the authenticated Supabase access/presence/meeting path.

Camera Ahead is therefore a **perception adapter**, not a new map, identity
system, or command center.

## v0.1 contract

Input:

```json
{
  "lat": 52.4,
  "lon": 16.9,
  "heading_deg": 90,
  "max_distance_m": 5000
}
```

Camera registry item:

```json
{
  "camera_id": "operator:id",
  "name": "human readable point",
  "lat": 52.4,
  "lon": 16.9,
  "source": "official/open-data operator",
  "image_url": "https://...",
  "public": true,
  "observed_at": 1790000000
}
```

Output candidates contain distance, bearing, angular offset, freshness, and a
score. The module never fetches video by itself.

## Selection logic

1. Derive heading from the last two reliable GPS samples when needed.
2. Keep only records explicitly marked `public=true`.
3. Keep cameras inside a forward cone (default ±55°).
4. Reject cameras farther than the requested horizon.
5. Reject stale records when a source provides timestamps.
6. Rank by distance + angular offset + freshness.
7. Vision analysis happens only after a candidate has been selected.

## First external sources

### GDDKiA

The official GDDKiA road-information service publicly exposes current road
conditions and camera imagery for selected national roads. This is the first
source to integrate around Poznań because it is purpose-built for public road
information.

### Poznań municipal monitoring

Poznań has a large municipal CCTV system, but its monitoring feeds are operated
by city services and are not treated here as public streams. We may use public
metadata/map information, but **not** attempt to access restricted feeds.

### Other webcams/open-data systems

Additional sources may be added only when the operator intentionally publishes
the current image/stream for public use. Each adapter must preserve source,
timestamp, and public-access provenance.

## Privacy/safety boundary

Camera Ahead is for situational awareness, not persistent tracking of people.

- no private/restricted CCTV;
- no credential bypass or feed enumeration;
- no face-search across public cameras;
- no long-term storage of bystander imagery;
- prefer a short-lived latest-frame analysis;
- return evidence source + image timestamp with each answer.

## Integration path

```text
Live Map GPS
   ↓
movement heading
   ↓
Camera Ahead selector
   ↓
fresh public camera frame(s)
   ↓
Vision: road / crowd / obstruction / weather / visibility
   ↓
"what is ahead?" answer with timestamp + source
```

Production Live Map and Supabase stay unchanged until this selector and at least
one public camera adapter pass isolated tests.


## GDDKiA adapter discovery — 2026-10-27

The current public-map JavaScript declares:

\`\`\`text
rootDataUrl = https://kpd.gddkia.gov.pl/amp/
camerapointsUrl = api/waypoints/camerapoints.json
\`\`\`

Therefore the camera-point transport URL used by the map is:

\`\`\`text
https://kpd.gddkia.gov.pl/amp/api/waypoints/camerapoints.json
\`\`\`

The JavaScript consumes point fields including:

- \`id\`, \`latitude\`, \`longitude\`, \`name\`;
- \`road_number\`, \`mileage\`;
- \`cameras[].images[].path\`;
- \`cameras[].images[].updated_date\`;
- \`meteo_stations\` for camera points that also expose weather data.

A direct anonymous fetch observed during this LAB returned HTTP 401. This is
treated as an access boundary, not an invitation to work around it.

\`src/gddkia_camera_adapter.py\` therefore separates **transport** from
**parsing**. It can parse the real KPD payload shape, but a live fetch must be
provided by a legitimate official public-map browser session if the endpoint
requires one.

Current LAB tests:

\`\`\`text
camera-ahead selector: 5 tests
GDDKiA adapter:       6 tests
\`\`\`

No production Live Map, Supabase function, Android bridge, or credential store
was changed by this work.

### Next integration seam

\`\`\`text
official public GDDKiA map session
        ↓
sanitized camera-point payload
        ↓
gddkia_camera_adapter.parse_camerapoints
        ↓
camera_ahead.select_cameras_ahead
        ↓
freshest selected public image
        ↓
vision summary + source + timestamp
\`\`\`

The session handoff should export only the public camera metadata needed by the
selector; it should not export browser cookies, credentials, or unrelated
session state.


## Headless owner context (canonical)

Owner location is **not** supplied by the Live Map UI and is **not** exposed through the public Camera Broker.

Canonical agent path:

1. `genesis_internal.owner_location_start_v01(force)` enqueues one bounded `workspace_python` command on `oneplus10t-b40`.
2. The device runs `~/GenesisProjects/InteropLab/genesis_location_snapshot_v01.py`.
3. The script requests one `termux-location` GPS snapshot and persists nothing locally.
4. `genesis_internal.owner_location_finish_v01(command_id)` validates the verified command receipt, freshness, coordinates, accuracy, speed, and GPS bearing.
5. Only one row, `live_map_presence.session_hash='owner-current'`, is upserted. No route history is stored.
6. `genesis_internal.owner_location_get_v01()` treats the row as fresh for 90 seconds.
7. Public `anon` and `authenticated` roles have no EXECUTE privilege on these functions.
8. The public Camera Broker remains public-camera-data only; it contains no owner-location endpoints.

Direction policy:
- when moving at >= 0.8 m/s, use GPS bearing;
- when slower, preserve only a recently verified heading (<=5 min) or report direction as unknown;
- do not infer a heading from the current Termux Rotation Vector output until its representation is independently calibrated.

This keeps the control path agent-first and UI-independent: no browser page or visual map is required for JARVIS to locate the owner.


## JARVIS eyes on-demand canonical v1

Canonical runtime is UI-independent and battery-safe.

### Owner location
- Private functions live in `genesis_internal`; `anon` and `authenticated` have no EXECUTE.
- `owner_location_start_v01(force)` first checks the `oneplus10t-b40` heartbeat.
- If heartbeat age is over 45 s, it returns `bridge_unavailable` and does **not** enqueue GPS.
- Fresh requests are submitted through canonical `bridge40_submit_command`, not direct `bridge30_commands` inserts.
- The device executes `~/GenesisProjects/InteropLab/genesis_location_snapshot_v01.py` (ECO v3 contract).
- Location is enabled only when it was initially off, one bounded `termux-location` snapshot is taken, then the original Location state must be restored and verified.
- Raw GPS history is not stored. Only `live_map_presence.session_hash='owner-current'` is overwritten; TTL is 90 s.
- Stale pending location commands are expired instead of replayed later.

### Public eyes registry
- `genesis_internal.public_eye_registry_v01` stores metadata only: name, coordinates, operator, source page, operational state, and optional Broker source id.
- It stores no JPEG, HLS segment, MP4, or other raw media.
- States are separated into `LIVE_VERIFIED`, `SOURCE_LIVE_PAGE`, `UNKNOWN`, and `OFFLINE_REPORTED`.
- Automatic selection excludes uncertain/offline entries by default.

### Agent API
- `jarvis_eyes_start_v01('nearby'|'ahead')`
  - uses a still-fresh owner snapshot immediately;
  - otherwise starts one on-demand GPS snapshot;
  - refuses to start GPS when Bridge is stale.
- `jarvis_eyes_finish_v01(command_id, mode)`
  - finalizes the verified GPS receipt;
  - returns either nearest public eyes or eyes inside the forward cone.
- `nearest_public_eyes_v01` sorts literally by distance and also returns a separately ranked `best_eye` for reliable Vision.
- `public_eyes_ahead_v01` uses GPS/recent verified heading and labels reused low-speed heading explicitly.

Battery invariant: no continuous GPS polling, no camera polling, and no raw camera-media persistence in Supabase.
