#!/usr/bin/env python3
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL="https://www.webcamera.pl/mapa"
OUT=Path("data/public_eyes/webcamera_registry.json")

def fetch_text(url):
    req=urllib.request.Request(url,headers={
        "User-Agent":"GENESIS-Public-Eyes-LAB/0.1 (+metadata-only)",
        "Accept":"text/html,application/xhtml+xml"
    })
    with urllib.request.urlopen(req,timeout=30) as r:
        if r.status != 200:
            raise RuntimeError(f"http_{r.status}")
        return r.read().decode("utf-8","replace")

def extract_markers(html):
    marker="var MAP_MARKERS = "
    pos=html.find(marker)
    if pos<0:
        raise RuntimeError("MAP_MARKERS_not_found")
    start=html.find("{",pos+len(marker))
    if start<0:
        raise RuntimeError("MAP_MARKERS_object_not_found")
    obj,end=json.JSONDecoder().raw_decode(html[start:])
    if not isinstance(obj,dict):
        raise RuntimeError("MAP_MARKERS_not_object")
    return obj

def premium_hint(slug,item):
    s=" ".join([
        slug,
        str(item.get("name") or ""),
        str(item.get("url") or ""),
        " ".join(map(str,item.get("tags") or []))
    ]).lower()
    return "premium" in s

def outdoor_score(item):
    s=" ".join([
        str(item.get("name") or ""),
        str(item.get("img_alt") or ""),
        str(item.get("img_title") or ""),
        " ".join(map(str,item.get("tags") or []))
    ]).lower()
    positive=("rynek","miasto","ulica","droga","deptak","plaża","morze","góry","jezioro","marina","panorama","centrum","park","stok","molo","port","most","lotnisko")
    negative=("parafia","kościół","cerkiew","ołtarz","msza","pasieka","pszczo")
    score=sum(1 for x in positive if x in s)-2*sum(1 for x in negative if x in s)
    return max(-5,min(10,score))

def main():
    html=fetch_text(URL)
    markers=extract_markers(html)
    eyes=[]
    inactive=0
    invalid=0
    for slug,item in markers.items():
        if not isinstance(item,dict):
            continue
        if bool(item.get("is_inactive")):
            inactive+=1
            continue
        try:
            lat=float(item.get("lat"))
            lon=float(item.get("lng"))
            if not (-90<=lat<=90 and -180<=lon<=180):
                raise ValueError
        except Exception:
            invalid+=1
            continue
        slug=str(item.get("cam") or slug).strip()[:160]
        tags=[str(x)[:80] for x in (item.get("tags") or [])[:24]]
        eyes.append({
            "id":"webcamera:"+slug,
            "provider":"webcamera.pl",
            "slug":slug,
            "name":str(item.get("name") or slug).strip()[:240],
            "lat":lat,
            "lon":lon,
            "page_url":str(item.get("url") or "").strip()[:700],
            "preview_url":"https://imageserver.webcamera.pl/miniaturki/"+slug+".jpg",
            "premium_hint":premium_hint(slug,item),
            "outdoor_score":outdoor_score(item),
            "tags":tags,
            "availability":"probe_on_demand",
            "image_persistence":"forbidden"
        })
    eyes.sort(key=lambda x:x["id"])
    payload={
        "schema":"GENESIS_PUBLIC_EYES_REGISTRY_V01",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "source_url":URL,
        "provider":"webcamera.pl",
        "policy":{
            "metadata_only":True,
            "raw_images_stored":False,
            "availability_probe":"on_demand_nearest_candidates_only",
            "premium_hint_default":"do_not_use_without_public_preview"
        },
        "counts":{
            "map_entries":len(markers),
            "active_with_valid_coords":len(eyes),
            "inactive_skipped":inactive,
            "invalid_coords_skipped":invalid,
            "premium_hint":sum(1 for x in eyes if x["premium_hint"]),
            "outdoor_positive":sum(1 for x in eyes if x["outdoor_score"]>0)
        },
        "eyes":eyes
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(payload["counts"],ensure_ascii=False))
    return 0

if __name__=="__main__":
    sys.exit(main())
