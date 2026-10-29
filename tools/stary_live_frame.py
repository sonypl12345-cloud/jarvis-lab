#!/usr/bin/env python3
import json, time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL="https://poznan-stary-rynek.webcamera.pl/"
OUT=Path("data/stary_live_frame.png")
META=Path("data/stary_live_frame.json")
OUT.parent.mkdir(parents=True,exist_ok=True)

def main():
    meta={"source":URL,"captured_at_epoch":time.time(),"ok":False}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--autoplay-policy=no-user-gesture-required","--disable-dev-shm-usage"])
        ctx=browser.new_context(viewport={"width":1280,"height":900},locale="pl-PL")
        page=ctx.new_page()
        page.goto(URL,wait_until="domcontentloaded",timeout=90000)

        for label in ("Akceptuję","Zgadzam się","Accept","OK","Zamknij"):
            try:
                loc=page.get_by_text(label,exact=True)
                if loc.count() and loc.first.is_visible():
                    loc.first.click(timeout=2500)
                    time.sleep(1)
                    break
            except Exception:
                pass

        deadline=time.time()+55
        chosen=None
        info=None
        while time.time()<deadline:
            for frame in page.frames:
                try:
                    vids=frame.locator("video")
                    for i in range(vids.count()):
                        v=vids.nth(i)
                        if not v.is_visible():
                            continue
                        try:
                            frame.evaluate("""(el)=>{el.muted=true; el.volume=0; const p=el.play(); if(p&&p.catch)p.catch(()=>{});}""",v.element_handle())
                        except Exception:
                            pass
                        try:
                            d=v.evaluate("""el=>({
                              readyState:el.readyState,
                              currentTime:el.currentTime,
                              videoWidth:el.videoWidth,
                              videoHeight:el.videoHeight,
                              paused:el.paused,
                              ended:el.ended,
                              src:el.currentSrc||el.src||""
                            })""")
                        except Exception:
                            continue
                        if d.get("readyState",0)>=2 and d.get("videoWidth",0)>=320 and d.get("videoHeight",0)>=180:
                            chosen=v
                            info=d
                            break
                    if chosen: break
                except Exception:
                    pass
            if chosen: break
            time.sleep(2)

        if not chosen:
            meta.update({"ok":False,"error":"live_video_not_ready","page_url":page.url,"frames":[f.url for f in page.frames]})
            page.screenshot(path=str(OUT),full_page=False)
        else:
            t0=float(info.get("currentTime") or 0)
            time.sleep(4)
            try:
                info2=chosen.evaluate("""el=>({
                  readyState:el.readyState,currentTime:el.currentTime,
                  videoWidth:el.videoWidth,videoHeight:el.videoHeight,
                  paused:el.paused,ended:el.ended,src:el.currentSrc||el.src||""
                })""")
            except Exception:
                info2=info
            advanced=float(info2.get("currentTime") or 0)>t0+0.5
            chosen.screenshot(path=str(OUT))
            meta.update({
                "ok":True,
                "live_advanced":advanced,
                "before_current_time":t0,
                "after_current_time":float(info2.get("currentTime") or 0),
                "video_width":info2.get("videoWidth"),
                "video_height":info2.get("videoHeight"),
                "ready_state":info2.get("readyState"),
                "paused":info2.get("paused"),
                "page_url":page.url
            })
        META.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
        browser.close()
    print(json.dumps(meta,ensure_ascii=False))
    return 0 if meta.get("ok") and meta.get("live_advanced") else 2

if __name__=="__main__":
    raise SystemExit(main())
