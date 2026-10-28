#!/usr/bin/env python3
import json
import sys
import time
from pathlib import Path
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

URL = "https://drogi.gddkia.gov.pl/mapy/mapa-informacji-drogowej"
CAMERA_URL = "https://kpd.gddkia.gov.pl/amp/api/waypoints/camerapoints.json"
OUT = Path("data/gddkia_registry_probe.json")

EXTRACT = r"""
() => {
  const text=(v,n=240)=>String(v??'').trim().slice(0,n);
  const app=(typeof mapApp!=='undefined'&&mapApp)?mapApp:window.mapApp;
  const layer=app&&typeof app.getLayer==='function'?app.getLayer('CamerapointsLayer'):null;
  if(!layer||typeof layer.getFeatures!=='function'){
    return {ok:false,stage:!app?'mapApp':'CamerapointsLayer',url:location.href,title:document.title};
  }
  const features=layer.getFeatures()||[];
  const points=features.slice(0,5000).map((feature,index)=>{
    const p=(feature&&feature.properties) ||
      (feature&&typeof feature.getProperties==='function'?feature.getProperties():{}) || {};
    let latitude=Number(p.latitude);
    let longitude=Number(p.longitude);
    if(!Number.isFinite(latitude)||!Number.isFinite(longitude)){
      try{
        const g=feature&&typeof feature.getGeometry==='function'?feature.getGeometry():null;
        const c=g&&typeof g.getCoordinates==='function'?g.getCoordinates():null;
        if(Array.isArray(c)&&c.length>=2&&Math.abs(Number(c[1]))<=90&&Math.abs(Number(c[0]))<=180){
          longitude=Number(c[0]); latitude=Number(c[1]);
        }
      }catch(_){}
    }
    const cameras=Array.isArray(p.cameras)?p.cameras.slice(0,12).map((camera,ci)=>({
      id:text(camera&&camera.id!==undefined?camera.id:ci,80),
      images:Array.isArray(camera&&camera.images)?camera.images.slice(0,12).map(image=>({
        path:text(image&&image.path,700),
        updated_date:text(image&&image.updated_date,100)
      })).filter(image=>image.path):[]
    })):[];
    return{
      id:text(p.id||index,120),latitude,longitude,
      name:text(p.name,240),road_number:text(p.road_number,40),
      mileage:p.mileage??null,owner:text(p.owner,120),
      source_name:text(p.source_name,120),cameras
    };
  }).filter(p=>Number.isFinite(p.latitude)&&Number.isFinite(p.longitude));
  return {ok:true,page:{url:location.href,title:document.title},layer_code:'CamerapointsLayer',feature_count:features.length,points};
}
"""

def unwrap_points(value):
    for _ in range(4):
        if isinstance(value,list):
            return [x for x in value if isinstance(x,dict)]
        if isinstance(value,dict) and "response" in value:
            value=value["response"]
            continue
        break
    return None

def sanitize(points):
    clean=[]
    for i,p in enumerate(points or []):
        try:
            lat=float(p.get("latitude"))
            lon=float(p.get("longitude"))
        except Exception:
            continue
        cams=[]
        raw_cams=p.get("cameras")
        if isinstance(raw_cams,list):
            for ci,cam in enumerate(raw_cams[:12]):
                if not isinstance(cam,dict):
                    continue
                images=[]
                raw_images=cam.get("images")
                if isinstance(raw_images,list):
                    for image in raw_images[:12]:
                        if not isinstance(image,dict):
                            continue
                        path=str(image.get("path") or "").strip()[:700]
                        if path:
                            images.append({
                                "path":path,
                                "updated_date":str(image.get("updated_date") or "").strip()[:100]
                            })
                cams.append({"id":str(cam.get("id",ci))[:80],"images":images})
        clean.append({
            "id":str(p.get("id",i))[:120],
            "latitude":lat,"longitude":lon,
            "name":str(p.get("name") or "").strip()[:240],
            "road_number":str(p.get("road_number") or "").strip()[:40],
            "mileage":p.get("mileage"),
            "owner":str(p.get("owner") or "").strip()[:120],
            "source_name":str(p.get("source_name") or "").strip()[:120],
            "cameras":cams,
        })
    return clean

def summary(payload):
    points=payload["points"]
    with_images=sum(1 for pt in points if any(cam.get("images") for cam in pt.get("cameras",[])))
    images=sum(len(cam.get("images",[])) for pt in points for cam in pt.get("cameras",[]))
    sample=[]
    for pt in points:
        for cam in pt.get("cameras",[]):
            if cam.get("images"):
                sample.append({
                    "id":pt.get("id"),"name":pt.get("name"),"road":pt.get("road_number"),
                    "lat":pt.get("latitude"),"lon":pt.get("longitude"),
                    "camera_id":cam.get("id"),"image":cam["images"][0]
                })
                if len(sample)>=5: break
        if len(sample)>=5: break
    return {"ok":True,"point_count":len(points),"points_with_images":with_images,"image_records":images,"sample":sample}

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    captured=[]
    diagnostics={"responses":[],"frames":[],"fetch_attempts":[]}

    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--disable-dev-shm-usage"])
        context=browser.new_context(
            locale="pl-PL",viewport={"width":1280,"height":900},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
        )
        page=context.new_page()

        def on_response(resp):
            u=resp.url
            low=u.lower()
            if any(k in low for k in ("camerapoint","waypoint","/amp/api/","kpd.gddkia.gov.pl")):
                diagnostics["responses"].append({"url":u[:1000],"status":resp.status})
            if "camerapoints.json" in low:
                try:
                    raw=resp.json()
                    pts=unwrap_points(raw)
                    if pts is not None:
                        captured.append({"transport":"network_response","url":u,"points":sanitize(pts)})
                except Exception as exc:
                    diagnostics["responses"].append({"url":u[:1000],"status":resp.status,"parse_error":str(exc)[:500]})

        page.on("response",on_response)
        page.goto(URL,wait_until="domcontentloaded",timeout=90000)

        # Consent is not needed for public data, but the site may defer optional scripts until the dialog is closed.
        for label in ("Akceptuję","Zamknij"):
            try:
                loc=page.get_by_text(label,exact=True)
                if loc.count() and loc.first.is_visible():
                    loc.first.click(timeout=3000)
                    time.sleep(2)
                    break
            except Exception:
                pass

        # Try to activate a camera-labelled UI control if the layer is opt-in.
        for frame in page.frames:
            try:
                loc=frame.locator("[title*='kamer' i], [aria-label*='kamer' i], [data-title*='kamer' i]")
                if loc.count():
                    for i in range(min(loc.count(),10)):
                        try:
                            if loc.nth(i).is_visible():
                                loc.nth(i).click(timeout=2000)
                                time.sleep(3)
                                break
                        except Exception:
                            pass
            except Exception:
                pass

        deadline=time.time()+60
        last=None
        result=None
        while time.time()<deadline:
            # Preferred: sanitized layer object in any same-origin frame.
            for frame in page.frames:
                try:
                    r=frame.evaluate(EXTRACT)
                    if r and r.get("ok") and r.get("points"):
                        result={"transport":"map_layer","feature_count":r.get("feature_count"),"points":r["points"]}
                        break
                    last=r
                except Exception as exc:
                    last={"exception":str(exc),"frame":frame.url}
            if result or captured:
                break

            # Browser-session fetch: same public session, but only camera JSON leaves the browser.
            for frame in page.frames:
                try:
                    f=frame.evaluate("""async (u) => {
                      try {
                        const r=await fetch(u,{credentials:'include',headers:{'Accept':'application/json'}});
                        const text=await r.text();
                        return {url:location.href,status:r.status,contentType:r.headers.get('content-type')||'',text:text.slice(0,5000000)};
                      } catch(e) { return {url:location.href,error:String(e)}; }
                    }""",CAMERA_URL)
                    diagnostics["fetch_attempts"].append({k:v for k,v in f.items() if k!="text"})
                    if f.get("status")==200 and f.get("text"):
                        raw=json.loads(f["text"])
                        pts=unwrap_points(raw)
                        if pts is not None:
                            captured.append({"transport":"browser_fetch","url":CAMERA_URL,"points":sanitize(pts)})
                            break
                except Exception as exc:
                    diagnostics["fetch_attempts"].append({"frame":frame.url,"exception":str(exc)[:500]})
            if captured:
                break
            time.sleep(3)

        if result:
            points=sanitize(result["points"])
            transport=result["transport"]
            feature_count=result.get("feature_count")
        elif captured:
            best=max(captured,key=lambda x:len(x["points"]))
            points=best["points"]; transport=best["transport"]; feature_count=len(points)
        else:
            diagnostics["frames"]=[f.url for f in page.frames]
            try:
                diagnostics["camera_elements"]=page.evaluate("""() => [...document.querySelectorAll('*')]
                  .filter(e=>/kamer|camera/i.test((e.id||'')+' '+(e.className||'')+' '+(e.getAttribute?.('title')||'')+' '+(e.getAttribute?.('aria-label')||'')))
                  .slice(0,80).map(e=>({tag:e.tagName,id:e.id||'',class:String(e.className||'').slice(0,300),title:e.getAttribute?.('title')||'',aria:e.getAttribute?.('aria-label')||''}))""")
            except Exception:
                pass
            diagnostics["last"]=last
            Path("data/gddkia_probe_diagnostics.json").write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2),encoding="utf-8")
            page.screenshot(path="data/gddkia_probe_failure.png",full_page=True)
            print(json.dumps({"ok":False,"diagnostics":diagnostics},ensure_ascii=False))
            browser.close()
            return 2

        payload={
            "schema":"GENESIS_GDDKIA_PUBLIC_CAMERA_REGISTRY_PROBE_V02",
            "captured_at_epoch":time.time(),
            "source_page":URL,
            "mode":"official_public_map_browser_session",
            "transport":transport,
            "feature_count":feature_count,
            "points":points,
            "boundary":"Sanitized public camera metadata only; no cookies, tokens, local/session storage, or unrelated page state."
        }
        OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(summary(payload)|{"transport":transport,"feature_count":feature_count},ensure_ascii=False))
        browser.close()
        return 0

if __name__=="__main__":
    sys.exit(main())
