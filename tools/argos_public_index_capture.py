#!/usr/bin/env python3
"""Refresh a metadata-only Central Europe eye window from ARGOS ATLAS public index.

The public index exposes only lightweight camera metadata. This script stores no
image/video bytes and never uses account/session endpoints.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

URL="https://argosatlas.com/api/cameras_index.json"
OUT=Path("data/public_eyes/argos_central_europe_registry.json")

# Poland plus a useful border halo. Camera Ahead will select by distance from the
# owner, so keeping neighboring-border eyes is useful and avoids pretending that
# a rectangular filter is an exact national boundary.
BBOX={
    "lat_min":48.8,
    "lat_max":55.2,
    "lon_min":13.8,
    "lon_max":24.5,
}

def fetch_json(url: str):
    req=urllib.request.Request(url,headers={
        "User-Agent":"GENESIS-Public-Eyes-LAB/0.2 (+metadata-only)",
        "Accept":"application/json",
    })
    with urllib.request.urlopen(req,timeout=45) as r:
        if r.status != 200:
            raise RuntimeError(f"http_{r.status}")
        if "json" not in (r.headers.get("Content-Type") or "").lower():
            raise RuntimeError("unexpected_content_type")
        return json.load(r)

def clean_heading(value):
    try:
        h=float(value)
    except (TypeError,ValueError):
        return None
    if not (-100000 < h < 100000):
        return None
    return h % 360.0

def priority(category: str) -> int:
    c=(category or "").lower()
    if c=="trafico":
        return 0
    if c=="urbanas":
        return 1
    if c=="medioambientales":
        return 2
    return 3

def main():
    rows=fetch_json(URL)
    if not isinstance(rows,list) or not rows:
        raise RuntimeError("argos_index_not_array")

    eyes=[]
    skipped=0
    for row in rows:
        if not isinstance(row,dict):
            skipped+=1
            continue
        try:
            lat=float(row.get("lat"))
            lon=float(row.get("lon"))
        except (TypeError,ValueError):
            skipped+=1
            continue
        if not (BBOX["lat_min"]<=lat<=BBOX["lat_max"] and BBOX["lon_min"]<=lon<=BBOX["lon_max"]):
            continue
        eye_id=str(row.get("id") or "").strip()
        if not eye_id or len(eye_id)>128:
            skipped+=1
            continue
        category=str(row.get("category") or "").strip()[:80]
        media_type=str(row.get("media_type") or "image").strip()[:40]
        heading=clean_heading(row.get("h"))
        heading_conf=str(row.get("hc") or "").strip()[:20] or None
        eyes.append({
            "id":"argos:"+eye_id,
            "provider":"argosatlas_public_index",
            "provider_id":eye_id,
            "name":str(row.get("name") or eye_id).strip()[:240],
            "lat":lat,
            "lon":lon,
            "category":category,
            "media_type":media_type,
            "heading_deg":heading,
            "heading_conf":heading_conf,
            "source_priority":priority(category),
            "feature_url":f"https://argosatlas.com/api/cam/{eye_id}/feature",
            "preview_url":f"https://argosatlas.com/api/cam/{eye_id}/image",
            "availability":"probe_on_demand",
            "freshness":"verify_on_demand",
            "image_persistence":"forbidden",
        })

    eyes.sort(key=lambda x:x["id"])
    cats=Counter(x["category"] or "unknown" for x in eyes)
    media=Counter(x["media_type"] or "unknown" for x in eyes)
    payload={
        "schema":"GENESIS_ARGOS_PUBLIC_EYES_WINDOW_V01",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "source_url":URL,
        "scope":{
            "kind":"central_europe_bbox",
            "bbox":BBOX,
            "note":"Useful Poland-plus-border window; not a political-boundary claim."
        },
        "policy":{
            "metadata_only":True,
            "raw_images_stored":False,
            "account_session_used":False,
            "candidate_details":"public_feature_endpoint_only",
            "candidate_images":"public_image_endpoint_on_demand_only",
            "probe_limit_default":3,
        },
        "counts":{
            "global_index_entries":len(rows),
            "window_entries":len(eyes),
            "with_heading":sum(1 for x in eyes if x["heading_deg"] is not None),
            "by_category":dict(sorted(cats.items())),
            "by_media_type":dict(sorted(media.items())),
            "invalid_rows_skipped":skipped,
        },
        "eyes":eyes,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload["counts"],ensure_ascii=False))
    return 0

if __name__=="__main__":
    sys.exit(main())
