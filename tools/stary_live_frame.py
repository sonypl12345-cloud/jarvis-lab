#!/usr/bin/env python3
import json, time, subprocess, shutil, sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin

HLS="https://hoktastream2.webcamera.pl/poznan_cam_a2ec1b/poznan_cam_a2ec1b.stream/playlist.m3u8"
OUT=Path("data/stary_live_frame.jpg")
META=Path("data/stary_live_frame.json")
OUT.parent.mkdir(parents=True,exist_ok=True)

UA="GENESIS-Stary-Rynek-Live-Frame-LAB/0.2"

def get_text(url,timeout=15):
    req=Request(url,headers={"User-Agent":UA,"Accept":"application/vnd.apple.mpegurl,application/x-mpegurl,*/*"})
    with urlopen(req,timeout=timeout) as r:
        return r.read().decode("utf-8","replace"),r.status,dict(r.headers)

def parse_master(text,base):
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    variants=[]
    for i,line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF:") and i+1<len(lines) and not lines[i+1].startswith("#"):
            variants.append(urljoin(base,lines[i+1]))
    return variants

def parse_media(text,base):
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    seq=None
    for line in lines:
        if line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            try: seq=int(line.split(":",1)[1])
            except: seq=None
    segs=[urljoin(base,x) for x in lines if not x.startswith("#") and ".ts" in x]
    return {"sequence":seq,"segments":segs,"latest_segment":segs[-1] if segs else None}

def main():
    meta={"source":HLS,"captured_at_epoch":time.time(),"ok":False}
    master,status,_=get_text(HLS)
    if status!=200 or "#EXTM3U" not in master:
        meta["error"]="master_unavailable"; META.write_text(json.dumps(meta,indent=2)); return 2
    variants=parse_master(master,HLS)
    media_url=variants[0] if variants else HLS

    m1,st1,_=get_text(media_url)
    p1=parse_media(m1,media_url)
    time.sleep(7)
    m2,st2,_=get_text(media_url)
    p2=parse_media(m2,media_url)

    advanced=(
        p1["sequence"] is not None and p2["sequence"] is not None and p2["sequence"]>p1["sequence"]
    ) or (
        p1["latest_segment"] and p2["latest_segment"] and p1["latest_segment"]!=p2["latest_segment"]
    )
    meta.update({"media_url":media_url,"first":p1,"second":p2,"live_advanced":bool(advanced)})
    if not advanced:
        meta["error"]="hls_not_advancing"; META.write_text(json.dumps(meta,ensure_ascii=False,indent=2)); return 3

    ffmpeg=shutil.which("ffmpeg")
    if not ffmpeg:
        meta["error"]="ffmpeg_missing"; META.write_text(json.dumps(meta,ensure_ascii=False,indent=2)); return 4

    cmd=[
      ffmpeg,"-hide_banner","-loglevel","error",
      "-live_start_index","-1",
      "-i",media_url,
      "-frames:v","1",
      "-q:v","2",
      "-vf","scale='min(1280,iw)':-2",
      "-y",str(OUT)
    ]
    try:
        cp=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
    except subprocess.TimeoutExpired:
        meta["error"]="ffmpeg_timeout"; META.write_text(json.dumps(meta,ensure_ascii=False,indent=2)); return 5

    if cp.returncode!=0 or not OUT.is_file() or OUT.stat().st_size<1000:
        meta.update({"error":"ffmpeg_capture_failed","returncode":cp.returncode,"stderr":(cp.stderr or "")[-2000:]})
        META.write_text(json.dumps(meta,ensure_ascii=False,indent=2)); return 6

    meta.update({
      "ok":True,
      "captured_at_epoch":time.time(),
      "bytes":OUT.stat().st_size,
      "live_advanced":True
    })
    META.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in meta.items() if k not in ("first","second")},ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
