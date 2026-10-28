"""Public visual-source registry for Camera Ahead LAB.

Only intentionally public sources are listed. Runtime health decides whether a
source is usable; the registry itself never attempts credentialed/private CCTV.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from .camera_ahead import CameraRecord


@dataclass(frozen=True)
class PublicVisualSource:
    source_id: str
    name: str
    lat: float
    lon: float
    source_page: str
    media_url: str
    media_kind: str
    provider: str
    scene_kind: str
    expected_refresh_s: Optional[int] = None
    max_stale_s: Optional[int] = None
    public: bool = True


SOURCES = (
    PublicVisualSource(
        source_id="webcamera:poznan-stary-rynek",
        name="Poznań — Stary Rynek",
        lat=52.407778,
        lon=16.934722,
        source_page="https://poznan-stary-rynek.webcamera.pl/",
        media_url=(
            "https://imageserver.webcamera.pl/miniaturki/"
            "poznan_cam_a2ec1b.stream.jpg"
        ),
        media_kind="snapshot",
        provider="WebCamera.pl",
        scene_kind="square",
        expected_refresh_s=300,
        max_stale_s=1800,
    ),
    PublicVisualSource(
        source_id="video-poznan:mtp-602",
        name="Poznań — MTP",
        lat=52.402119,
        lon=16.903809,
        source_page="https://video.poznan.pl/wideo/livestream/kamerka-mtp/",
        media_url="https://live.mtp.pl/cam1.ts/stream.m3u8",
        media_kind="hls",
        provider="Video Poznań / MTP",
        scene_kind="panorama",
    ),
    PublicVisualSource(
        source_id="lookcam:poznan-hetmanska",
        name="Poznań — Hetmańska",
        lat=52.390278,
        lon=16.894167,
        source_page="https://lookcam.com/poznan-hetmanska",
        media_url=(
            "https://api.lookcam.com/v1/streams/"
            "a4d74def-e6f3-4239-b8ce-00ea83b7d83c/thumbnail"
        ),
        media_kind="snapshot",
        provider="LookCam",
        scene_kind="road",
        max_stale_s=1800,
    ),
)


def snapshot_camera_records(
    sources: Iterable[PublicVisualSource],
    *,
    healthy_ids: Iterable[str],
) -> List[CameraRecord]:
    """Promote only runtime-health-verified public snapshot sources.

    observed_at remains None because HTTP retrieval time is not necessarily
    the image capture time.
    """
    healthy = set(healthy_ids)
    out: List[CameraRecord] = []
    for source in sources:
        if (
            not source.public
            or source.media_kind != "snapshot"
            or source.source_id not in healthy
        ):
            continue
        out.append(
            CameraRecord(
                camera_id=source.source_id,
                name=source.name,
                lat=source.lat,
                lon=source.lon,
                source=source.provider,
                image_url=source.media_url,
                public=True,
                observed_at=None,
            )
        )
    return out
