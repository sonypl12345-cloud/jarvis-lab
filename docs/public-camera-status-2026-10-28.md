# Public Camera Source Status — 2026-10-28

Camera Ahead now separates discovery, health, and selection.

A source being listed does not mean it is currently live. Before promotion to
the selector it must pass a bounded runtime health check.

## Poznań sources discovered

### WebCamera.pl — Stary Rynek

- Page: https://poznan-stary-rynek.webcamera.pl/
- Public embed: https://imageserver.webcamera.pl/umiesc/poznan-stary-rynek
- Snapshot:
  https://imageserver.webcamera.pl/miniaturki/poznan_cam_a2ec1b.stream.jpg
- Public embed documentation says the still image refreshes every few minutes.
- LAB probe on 2026-10-28: HTTP 200, JPEG.
- Scene type: public square / crowd / weather, not a road camera.

### Video Poznań / MTP — video 602

The public player config endpoint returned:

- HLS: https://live.mtp.pl/cam1.ts/stream.m3u8
- DASH: https://video.poznan.pl/dash/live02/stream.mpd

The player config itself was HTTP 200 without account login. During the
2026-10-28 LAB health check the HLS endpoint returned HTTP 503, so it must not
be promoted until a later health check succeeds.

### LookCam — Poznań Hetmańska

The public page exposes the camera UUID and a public thumbnail endpoint. Current
web indexing marks the stream offline. A LAB check found the thumbnail HTTP 200
but Last-Modified was Tue, 10 Feb 2026 22:40:40 GMT, and three cache-busted
samples were byte-identical. Therefore the thumbnail is stale and must not be
used as current road evidence.

Coordinates are approximate scene/source coordinates, suitable for source
selection only; they are not a claim about the exact optical center.

## Rule

registry -> runtime health -> selector -> vision

Never:

registry -> assume live
