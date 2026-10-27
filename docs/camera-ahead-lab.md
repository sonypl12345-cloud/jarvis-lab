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
