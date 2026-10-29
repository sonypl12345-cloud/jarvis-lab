Deno.serve(async(req)=>{
  const OWNER_CONTEXT_TTL_S=90;
  const PERSISTENCE_POLICY={
    raw_images:"forbidden",
    video_segments:"forbidden",
    storage_uploads:"forbidden",
    database_blobs:"forbidden",
    mode:"ephemeral_on_demand_only",
    max_frame_bytes:2000000
  };
  const STARY={
    id:"webcamera-stary-rynek",
    name:"Stary Rynek",
    operator:"webcamera.pl",
    public_page:"https://poznan-stary-rynek.webcamera.pl/",
    region:"Poznań",
    purpose:"public_city_view",
    lat:52.40763155230196,
    lon:16.932474616679546,
    orientation:"rotating_or_unknown",
    hls_url:"https://hoktastream2.webcamera.pl/poznan_cam_a2ec1b/poznan_cam_a2ec1b.stream/playlist.m3u8",
    latest_mp4:"https://imageserver.webcamera.pl/rec/poznan-stary-rynek/latest.mp4",
    preview_url:"https://imageserver.webcamera.pl/miniaturki/poznan_cam_a2ec1b.jpg",
    frame_ttl_s:180
  };

  const SOURCES=[
    STARY,
    {id:"poznan-mtp-live",name:"MTP",operator:"Urząd Miasta Poznania / Video Poznań",public_page:"https://video.poznan.pl/wideo/livestream/kamerka-mtp/",region:"Poznań",purpose:"public_city_view",config_url:"https://video.poznan.pl/player/build/db/index.php?video_id=602&autoplay=false&muted=true"},
    {id:"panorama-umww-s",name:"UMWW Południe",operator:"Panorama Poznania Online",public_page:"https://156.15.119.185-rev.hti.pl/",region:"Poznań",purpose:"public_panorama",preview_url:"https://156.15.119.185-rev.hti.pl/custom/img/s1.jpg",hls_url:"https://panorama.poznan.pl/hls/nimble1.m3u8"},
    {id:"panorama-umww-n",name:"UMWW Północ",operator:"Panorama Poznania Online",public_page:"https://156.15.119.185-rev.hti.pl/",region:"Poznań",purpose:"public_panorama",preview_url:"https://156.15.119.185-rev.hti.pl/custom/img/s2.jpg",hls_url:"https://panorama.poznan.pl/hls/nimble2.m3u8"},
    {id:"panorama-umww-e",name:"UMWW Wschód",operator:"Panorama Poznania Online",public_page:"https://156.15.119.185-rev.hti.pl/",region:"Poznań",purpose:"public_panorama",preview_url:"https://156.15.119.185-rev.hti.pl/custom/img/s3.jpg",hls_url:"https://panorama.poznan.pl/hls/nimble3.m3u8"},
    {id:"panorama-umww-w",name:"UMWW Zachód",operator:"Panorama Poznania Online",public_page:"https://156.15.119.185-rev.hti.pl/",region:"Poznań",purpose:"public_panorama",preview_url:"https://156.15.119.185-rev.hti.pl/custom/img/s4.jpg",hls_url:"https://panorama.poznan.pl/hls/nimble4.m3u8"}
  ];

  const out=(body,status=200)=>new Response(JSON.stringify(body),{
    status,
    headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}
  });

  const fetchT=async(url,init={},ms=7000)=>{
    const c=new AbortController();
    const timer=setTimeout(()=>c.abort(),ms);
    try{
      return await fetch(url,{
        ...init,
        signal:c.signal,
        redirect:"follow",
        headers:{
          ...(init.headers||{}),
          "user-agent":"GENESIS-Camera-Broker-LAB/0.14 (+registry-eyes;ephemeral-public-cameras;owner-context-private)"
        }
      });
    } finally { clearTimeout(timer); }
  };

  const absolute=(base,rel)=>new URL(rel,base).toString();

  const parseMaster=(text,base)=>{
    const lines=text.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
    const variants=[];
    for(let i=0;i<lines.length;i++){
      if(lines[i].startsWith("#EXT-X-STREAM-INF:") && lines[i+1] && !lines[i+1].startsWith("#")){
        variants.push(absolute(base,lines[i+1]));
      }
    }
    return variants;
  };

  const parseMedia=(text,base)=>{
    const lines=text.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
    const seqLine=lines.find(x=>x.startsWith("#EXT-X-MEDIA-SEQUENCE:"));
    const sequence=seqLine?Number(seqLine.split(":")[1]):null;
    const segments=lines.filter(x=>!x.startsWith("#") && /\.ts(?:\?|$)/i.test(x)).map(x=>absolute(base,x));
    return {sequence,segments,latest_segment:segments.length?segments[segments.length-1]:null};
  };

  async function staryStatus(waitForAdvance=false){
    const checked_at=new Date().toISOString();
    try{
      const masterRes=await fetchT(STARY.hls_url,{headers:{"accept":"application/vnd.apple.mpegurl,application/x-mpegurl,*/*"}});
      const master=await masterRes.text();
      if(!masterRes.ok || !master.includes("#EXTM3U")) throw new Error("master_manifest_unavailable");
      const variants=parseMaster(master,STARY.hls_url);
      const mediaUrl=variants[0]||STARY.hls_url;

      const readMedia=async()=>{
        const r=await fetchT(mediaUrl,{headers:{"accept":"application/vnd.apple.mpegurl,application/x-mpegurl,*/*"}});
        const t=await r.text();
        if(!r.ok || !t.includes("#EXTM3U")) throw new Error("media_manifest_unavailable");
        return parseMedia(t,mediaUrl);
      };

      const first=await readMedia();
      let second=null;
      if(waitForAdvance){
        await new Promise(resolve=>setTimeout(resolve,7000));
        second=await readMedia();
      }

      let mp4Probe=null;
      try{
        const h=await fetchT(STARY.latest_mp4,{method:"HEAD"},5000);
        mp4Probe={
          ok:h.ok,
          http_status:h.status,
          content_type:h.headers.get("content-type"),
          content_length:h.headers.get("content-length"),
          last_modified:h.headers.get("last-modified"),
          etag:h.headers.get("etag")
        };
      }catch(e){
        mp4Probe={ok:false,error:e instanceof Error?e.message:String(e)};
      }

      const advanced=second
        ? (
            (Number.isFinite(first.sequence) && Number.isFinite(second.sequence) && second.sequence>first.sequence) ||
            (first.latest_segment && second.latest_segment && first.latest_segment!==second.latest_segment)
          )
        : null;

      return {
        ok:true,
        source_id:STARY.id,
        name:STARY.name,
        checked_at,
        master_http_status:masterRes.status,
        resolution_hint:"1920x1080",
        media_playlist:mediaUrl,
        first,
        second,
        advanced,
        live:waitForAdvance?Boolean(advanced):Boolean(first.latest_segment),
        latest_mp4:{url:STARY.latest_mp4,...mp4Probe},
        vision_input:{
          type:"video_clip",
          url:STARY.latest_mp4,
          live_hls:STARY.hls_url,
          note:"Decode one frame from latest.mp4 or HLS for visual interpretation."
        },
        provenance:{
          public_page:STARY.public_page,
          operator:STARY.operator,
          region:STARY.region,
          lat:STARY.lat,
          lon:STARY.lon,
          orientation:STARY.orientation
        },
        boundary:"Public live camera only; no identity tracking, no private feeds, no recording."
      };
    }catch(e){
      return {ok:false,source_id:STARY.id,checked_at,error:e instanceof Error?e.message:String(e)};
    }
  }

  const parseEnv=raw=>{const a=raw.indexOf("{"),b=raw.lastIndexOf("}");if(a<0||b<=a)throw new Error("player_config_json_not_found");return JSON.parse(raw.slice(a,b+1))};

  const resolveMtp=async s=>{
    if(!s.config_url)return[];
    const r=await fetchT(s.config_url);
    if(!r.ok)throw new Error("config_http_"+r.status);
    const cfg=parseEnv((await r.text()).slice(0,128000));
    return Array.isArray(cfg?.sources?.hls)?cfg.sources.hls.map(x=>String(x?.url||"")).filter(Boolean):[];
  };

  const preview=async s=>{
    if(!s.preview_url)return null;
    try{
      const r=await fetchT(s.preview_url,{headers:{"accept":"image/jpeg,image/*;q=0.8,*/*;q=0.1"}},5000);
      const bytes=new Uint8Array(await r.arrayBuffer());
      const jpeg=bytes.length>=2&&bytes[0]===255&&bytes[1]===216;
      return {
        ok:r.ok&&jpeg,http_status:r.status,content_type:r.headers.get("content-type")||"",
        bytes:bytes.length,jpeg,last_modified:r.headers.get("last-modified"),
        etag:r.headers.get("etag"),image_url:s.preview_url
      };
    }catch(e){return{ok:false,error:e instanceof Error?e.message:String(e),image_url:s.preview_url}}
  };

  const hex=bytes=>Array.from(new Uint8Array(bytes)).map(b=>b.toString(16).padStart(2,"0")).join("");

  async function staryFrameMeta(){
    const checkedAt=new Date();
    const live=await staryStatus(false);
    if(!live.ok||!live.live){
      return {ok:false,error:"live_source_unavailable",live};
    }
    try{
      const r=await fetchT(STARY.preview_url,{
        headers:{
          "accept":"image/jpeg,image/*;q=0.8,*/*;q=0.1",
          "cache-control":"no-cache"
        }
      },5000);
      const declaredSize=Number(r.headers.get("content-length")||"0");
      if(declaredSize>PERSISTENCE_POLICY.max_frame_bytes){
        return {ok:false,source_id:STARY.id,checked_at:checkedAt.toISOString(),error:"frame_too_large",declared_bytes:declaredSize,max_bytes:PERSISTENCE_POLICY.max_frame_bytes};
      }
      const bytes=new Uint8Array(await r.arrayBuffer());
      if(bytes.length>PERSISTENCE_POLICY.max_frame_bytes){
        return {ok:false,source_id:STARY.id,checked_at:checkedAt.toISOString(),error:"frame_too_large",bytes:bytes.length,max_bytes:PERSISTENCE_POLICY.max_frame_bytes};
      }
      const jpeg=r.ok&&bytes.length>=2&&bytes[0]===255&&bytes[1]===216;
      const lm=r.headers.get("last-modified");
      const capturedAt=lm?new Date(lm):null;
      const ageS=capturedAt&&Number.isFinite(capturedAt.getTime())
        ? Math.max(0,(checkedAt.getTime()-capturedAt.getTime())/1000)
        : null;
      const digest=await crypto.subtle.digest("SHA-256",bytes);
      const fresh=jpeg&&ageS!==null&&ageS<=STARY.frame_ttl_s;
      return {
        ok:fresh,
        source_id:STARY.id,
        checked_at:checkedAt.toISOString(),
        captured_at:capturedAt&&Number.isFinite(capturedAt.getTime())?capturedAt.toISOString():null,
        age_s:ageS,
        ttl_s:STARY.frame_ttl_s,
        fresh,
        jpeg,
        bytes:bytes.length,
        sha256:hex(digest),
        content_type:r.headers.get("content-type"),
        etag:r.headers.get("etag"),
        image_url:STARY.preview_url,
        hls_sequence:live.first?.sequence,
        latest_segment:live.first?.latest_segment,
        provenance:live.provenance,
        boundary:live.boundary
      };
    }catch(e){
      return {ok:false,source_id:STARY.id,checked_at:checkedAt.toISOString(),error:e instanceof Error?e.message:String(e)};
    }
  }

  async function staryFrameResponse(){
    const live=await staryStatus(false);
    if(!live.ok||!live.live)return out({ok:false,error:"live_source_unavailable",detail:live},503);
    try{
      const r=await fetchT(STARY.preview_url,{
        headers:{
          "accept":"image/jpeg,image/*;q=0.8,*/*;q=0.1",
          "cache-control":"no-cache"
        }
      },5000);
      const declaredSize=Number(r.headers.get("content-length")||"0");
      if(declaredSize>PERSISTENCE_POLICY.max_frame_bytes){
        return out({ok:false,error:"frame_too_large",declared_bytes:declaredSize,max_bytes:PERSISTENCE_POLICY.max_frame_bytes},413);
      }
      const bytes=new Uint8Array(await r.arrayBuffer());
      if(bytes.length>PERSISTENCE_POLICY.max_frame_bytes){
        return out({ok:false,error:"frame_too_large",bytes:bytes.length,max_bytes:PERSISTENCE_POLICY.max_frame_bytes},413);
      }
      const jpeg=r.ok&&bytes.length>=2&&bytes[0]===255&&bytes[1]===216;
      const lm=r.headers.get("last-modified");
      const capturedAt=lm?new Date(lm):null;
      const now=new Date();
      const ageS=capturedAt&&Number.isFinite(capturedAt.getTime())
        ? Math.max(0,(now.getTime()-capturedAt.getTime())/1000)
        : null;
      if(!jpeg||ageS===null||ageS>STARY.frame_ttl_s){
        return out({
          ok:false,error:"frame_stale_or_invalid",jpeg,age_s:ageS,ttl_s:STARY.frame_ttl_s,
          captured_at:capturedAt&&Number.isFinite(capturedAt.getTime())?capturedAt.toISOString():null,
          hls_sequence:live.first?.sequence
        },503);
      }
      return new Response(bytes,{
        status:200,
        headers:{
          "content-type":"image/jpeg",
          "cache-control":"no-store",
          "x-genesis-source-id":STARY.id,
          "x-genesis-captured-at":capturedAt.toISOString(),
          "x-genesis-frame-age-s":String(Math.round(ageS)),
          "x-genesis-frame-ttl-s":String(STARY.frame_ttl_s),
          "x-genesis-hls-sequence":String(live.first?.sequence??""),
          "x-genesis-persistence":"ephemeral-no-store"
        }
      });
    }catch(e){
      return out({ok:false,error:"frame_fetch_failed",detail:e instanceof Error?e.message:String(e)},502);
    }
  }

  const resolvePublicEye=(eyeId)=>{
    const id=String(eyeId||"").trim();
    let m=id.match(/^webcamera:([A-Za-z0-9._-]{1,180})$/);
    if(m){
      return {
        eye_id:id,
        provider:"webcamera.pl",
        url:"https://imageserver.webcamera.pl/miniaturki/"+m[1]+".jpg",
        ttl_s:900,
        freshness_mode:"last_modified"
      };
    }
    m=id.match(/^argos:([0-9a-f]{18})$/);
    if(m){
      return {
        eye_id:id,
        provider:"argosatlas_public_index",
        url:"https://argosatlas.com/api/cam/"+m[1]+"/image",
        ttl_s:300,
        freshness_mode:"cache_bounded"
      };
    }
    return null;
  };

  const parseMaxAge=(value)=>{
    const m=String(value||"").match(/(?:^|[, ]+)max-age=([0-9]+)/i);
    return m?Number(m[1]):null;
  };

  async function publicEyeProbe(eyeId){
    const eye=resolvePublicEye(eyeId);
    if(!eye)return {ok:false,error:"eye_id_not_allowlisted"};
    try{
      const r=await fetchT(eye.url,{
        method:"HEAD",
        headers:{
          "accept":"image/jpeg,image/*;q=0.8,*/*;q=0.1",
          "cache-control":"no-cache"
        }
      },5000);
      const ct=String(r.headers.get("content-type")||"").toLowerCase();
      const len=Number(r.headers.get("content-length")||"0");
      const cc=r.headers.get("cache-control");
      const lm=r.headers.get("last-modified");
      const maxAge=parseMaxAge(cc);
      const now=new Date();
      const captured=lm?new Date(lm):null;
      const ageS=captured&&Number.isFinite(captured.getTime())
        ?Math.max(0,(now.getTime()-captured.getTime())/1000):null;
      const image=r.ok&&ct.startsWith("image/");
      const sizeOk=!Number.isFinite(len)||len<=0||len<=PERSISTENCE_POLICY.max_frame_bytes;
      const freshnessOk=eye.freshness_mode==="last_modified"
        ?(ageS!==null&&ageS<=eye.ttl_s)
        :(maxAge!==null&&maxAge<=eye.ttl_s);
      return {
        ok:Boolean(image&&sizeOk&&freshnessOk),
        eye_id:eye.eye_id,
        provider:eye.provider,
        checked_at:now.toISOString(),
        http_status:r.status,
        content_type:r.headers.get("content-type"),
        content_length:Number.isFinite(len)?len:null,
        cache_control:cc,
        cache_max_age_s:maxAge,
        last_modified:lm,
        age_s:ageS,
        ttl_s:eye.ttl_s,
        freshness_mode:eye.freshness_mode,
        freshness_ok:freshnessOk,
        image_url:eye.url,
        raw_media_persisted:false
      };
    }catch(e){
      return {ok:false,eye_id:eye.eye_id,provider:eye.provider,error:e instanceof Error?e.message:String(e),raw_media_persisted:false};
    }
  }

  async function publicEyeFrame(eyeId){
    const eye=resolvePublicEye(eyeId);
    if(!eye)return out({ok:false,error:"eye_id_not_allowlisted"},400);
    try{
      const u=eye.provider==="webcamera.pl"
        ?eye.url+(eye.url.includes("?")?"&":"?")+"genesis="+Date.now()
        :eye.url;
      const r=await fetchT(u,{
        headers:{
          "accept":"image/jpeg,image/*;q=0.8,*/*;q=0.1",
          "cache-control":"no-cache"
        }
      },6000);
      const declared=Number(r.headers.get("content-length")||"0");
      if(Number.isFinite(declared)&&declared>PERSISTENCE_POLICY.max_frame_bytes){
        return out({ok:false,error:"frame_too_large",declared_bytes:declared,max_bytes:PERSISTENCE_POLICY.max_frame_bytes},413);
      }
      const bytes=new Uint8Array(await r.arrayBuffer());
      if(bytes.length>PERSISTENCE_POLICY.max_frame_bytes){
        return out({ok:false,error:"frame_too_large",bytes:bytes.length,max_bytes:PERSISTENCE_POLICY.max_frame_bytes},413);
      }
      const jpeg=bytes.length>=2&&bytes[0]===255&&bytes[1]===216;
      const ct=String(r.headers.get("content-type")||"").toLowerCase();
      const cc=r.headers.get("cache-control");
      const lm=r.headers.get("last-modified");
      const maxAge=parseMaxAge(cc);
      const captured=lm?new Date(lm):null;
      const now=new Date();
      const ageS=captured&&Number.isFinite(captured.getTime())
        ?Math.max(0,(now.getTime()-captured.getTime())/1000):null;
      const freshnessOk=eye.freshness_mode==="last_modified"
        ?(ageS!==null&&ageS<=eye.ttl_s)
        :(maxAge!==null&&maxAge<=eye.ttl_s);
      if(!r.ok||!jpeg||!ct.startsWith("image/")||!freshnessOk){
        return out({
          ok:false,error:"frame_unavailable_or_stale",
          http_status:r.status,jpeg,content_type:r.headers.get("content-type"),
          age_s:ageS,cache_max_age_s:maxAge,ttl_s:eye.ttl_s,
          freshness_mode:eye.freshness_mode
        },503);
      }
      return new Response(bytes,{
        status:200,
        headers:{
          "content-type":"image/jpeg",
          "cache-control":"no-store",
          "x-genesis-eye-id":eye.eye_id,
          "x-genesis-provider":eye.provider,
          "x-genesis-frame-ttl-s":String(eye.ttl_s),
          "x-genesis-freshness-mode":eye.freshness_mode,
          "x-genesis-persistence":"ephemeral-no-store"
        }
      });
    }catch(e){
      return out({ok:false,error:"frame_fetch_failed",detail:e instanceof Error?e.message:String(e)},502);
    }
  }

  const probe=async s=>{
    if(s.id===STARY.id){
      const live=await staryStatus(false);
      const p=await preview(s);
      return {
        source_id:s.id,name:s.name,operator:s.operator,region:s.region,
        ok:Boolean(live.ok&&live.live),preview:p,stream:live,checked_at:new Date().toISOString()
      };
    }
    const p=await preview(s);
    let stream=null;
    try{
      const urls=s.hls_url?[s.hls_url]:await resolveMtp(s);
      if(urls.length){
        const r=await fetchT(urls[0],{},5000);
        const txt=(await r.text()).slice(0,64000);
        stream={ok:r.ok&&txt.includes("#EXTM3U"),http_status:r.status,is_hls_manifest:txt.includes("#EXTM3U"),hls_url:urls[0]};
      }
    }catch(e){stream={ok:false,error:e instanceof Error?e.message:String(e)}}
    return {source_id:s.id,name:s.name,operator:s.operator,region:s.region,ok:Boolean(p?.ok||stream?.ok),preview:p,stream,checked_at:new Date().toISOString()};
  };

  if(req.method==="GET")return out({
    ok:true,
    schema:"GENESIS_CAMERA_BROKER_LAB_V14",
    mode:"read_only_cloud_only",
    source_count:SOURCES.length,
    sources:SOURCES.map(({config_url,hls_url,latest_mp4,...s})=>s),
    stary_rynek:{
      live_transport:"HLS",
      vision_asset:"fresh_jpeg_with_hls_proof",
      frame_ttl_s:STARY.frame_ttl_s,
      coordinates:{lat:STARY.lat,lon:STARY.lon},
      orientation:STARY.orientation
    },
    persistence_policy:PERSISTENCE_POLICY,
    boundary:"Public camera sources only; raw images/video are never persisted to Supabase Storage or database; frames are fetched on demand and discarded after the response."
  });

  if(req.method!=="POST")return out({ok:false,error:"method_not_allowed"},405);
  let b={};try{b=await req.json()}catch{return out({ok:false,error:"invalid_json"},400)}

  if(["persist_frame","save_frame","archive_frame","upload_frame"].includes(String(b.action||""))){
    return out({ok:false,error:"persistence_forbidden_by_policy",policy:PERSISTENCE_POLICY},403);
  }

  if(b.action==="public_eye_probe") return out(await publicEyeProbe(b.eye_id));
  if(b.action==="public_eye_frame") return await publicEyeFrame(b.eye_id);

  if(b.action==="stary_rynek_live_status") return out(await staryStatus(false));
  if(b.action==="stary_rynek_frame_meta") return out(await staryFrameMeta());
  if(b.action==="stary_rynek_frame") return await staryFrameResponse();
  if(b.action==="stary_rynek_verify_live") return out(await staryStatus(true));

  if(b.action==="probe_source"){
    const s=SOURCES.find(x=>x.id===b.source_id);
    if(!s)return out({ok:false,error:"unknown_source"},404);
    return out(await probe(s));
  }

  if(b.action==="probe_all"){
    const r=await Promise.all(SOURCES.map(probe));
    return out({ok:true,schema:"GENESIS_CAMERA_BROKER_PROBE_V05",checked_at:new Date().toISOString(),total:r.length,live:r.filter(x=>x.ok).length,results:r});
  }

  if(b.action==="vision_input"){
    if(b.source_id===STARY.id){
      const live=await staryStatus(false);
      if(!live.ok||!live.live)return out({ok:false,error:"live_source_unavailable",detail:live},503);
      return out({
        ok:true,
        schema:"GENESIS_CAMERA_VISION_INPUT_V02",
        source_id:STARY.id,
        checked_at:live.checked_at,
        input:{type:"fresh_jpeg",action:"stary_rynek_frame",fallback:live.vision_input},
        provenance:live.provenance,
        freshness:{media_sequence:live.first?.sequence,latest_segment:live.first?.latest_segment},
        boundary:live.boundary
      });
    }
    const eye=resolvePublicEye(b.source_id);
    if(!eye)return out({ok:false,error:"vision_input_not_ready_for_source"},404);
    const health=await publicEyeProbe(eye.eye_id);
    if(!health.ok)return out({ok:false,error:"public_eye_unavailable",health},503);
    return out({
      ok:true,
      schema:"GENESIS_CAMERA_VISION_INPUT_V02",
      source_id:eye.eye_id,
      checked_at:health.checked_at,
      input:{type:"fresh_jpeg",action:"public_eye_frame",eye_id:eye.eye_id},
      freshness:health,
      boundary:"Public intentionally exposed camera snapshot only; no credentials, no private feeds, no identity tracking, no persistence."
    });
  }

  return out({ok:false,error:"unsupported_action",allowed:["public_eye_probe","public_eye_frame","probe_source","probe_all","stary_rynek_live_status","stary_rynek_verify_live","stary_rynek_frame_meta","stary_rynek_frame","vision_input"]},400);
});