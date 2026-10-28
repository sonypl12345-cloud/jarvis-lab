#!/usr/bin/env python3
import json
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://drogi.gddkia.gov.pl/mapy/mapa-informacji-drogowej"
OUT = Path("data/gddkia_registry_probe.json")

EXTRACT = r"""
() => {
  const text=(v,n=240)=>String(v??'').trim().slice(0,n);
  const app=window.mapApp;
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
        if(Array.isArray(c)&&c.length>=2){
          // KPD may expose projected coordinates here, so use only plausible WGS84.
          if(Math.abs(Number(c[1]))<=90&&Math.abs(Number(c[0]))<=180){
            longitude=Number(c[0]); latitude=Number(c[1]);
          }
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
      id:text(p.id||index,120),
      latitude,longitude,
      name:text(p.name,240),
      road_number:text(p.road_number,40),
      mileage:p.mileage??null,
      owner:text(p.owner,120),
      source_name:text(p.source_name,120),
      cameras
    };
  }).filter(p=>Number.isFinite(p.latitude)&&Number.isFinite(p.longitude));
  return {
    ok:true,
    page:{url:location.href,title:document.title},
    layer_code:'CamerapointsLayer',
    feature_count:features.length,
    points
  };
}
"""

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--disable-dev-shm-usage"])
        context=browser.new_context(
            locale="pl-PL",
            viewport={"width":1280,"height":900},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
        )
        page=context.new_page()
        page.goto(URL,wait_until="domcontentloaded",timeout=90000)
        deadline=time.time()+75
        result=None
        last=None
        while time.time()<deadline:
            try:
                result=page.evaluate(EXTRACT)
                if result and result.get("ok") and result.get("points"):
                    break
                last=result
            except Exception as exc:
                last={"exception":str(exc)}
            time.sleep(2)
        if not result or not result.get("ok"):
            print(json.dumps({"ok":False,"last":last,"url":page.url},ensure_ascii=False))
            page.screenshot(path="data/gddkia_probe_failure.png",full_page=True)
            browser.close()
            return 2
        payload={
            "schema":"GENESIS_GDDKIA_PUBLIC_CAMERA_REGISTRY_PROBE_V01",
            "captured_at_epoch":time.time(),
            "source_page":URL,
            "mode":"official_public_map_browser_session",
            "feature_count":result.get("feature_count"),
            "points":result["points"],
            "boundary":"Sanitized public camera metadata only; no cookies, tokens, local/session storage, or unrelated page state."
        }
        OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        with_images=sum(
            1 for pt in payload["points"]
            if any(cam.get("images") for cam in pt.get("cameras",[]))
        )
        images=sum(
            len(cam.get("images",[]))
            for pt in payload["points"]
            for cam in pt.get("cameras",[])
        )
        sample=[]
        for pt in payload["points"]:
            for cam in pt.get("cameras",[]):
                if cam.get("images"):
                    sample.append({
                        "id":pt.get("id"),"name":pt.get("name"),
                        "road":pt.get("road_number"),"lat":pt.get("latitude"),
                        "lon":pt.get("longitude"),"camera_id":cam.get("id"),
                        "image":cam["images"][0]
                    })
                    if len(sample)>=5: break
            if len(sample)>=5: break
        print(json.dumps({
            "ok":True,
            "feature_count":payload["feature_count"],
            "point_count":len(payload["points"]),
            "points_with_images":with_images,
            "image_records":images,
            "sample":sample
        },ensure_ascii=False))
        browser.close()
        return 0

if __name__=="__main__":
    sys.exit(main())
