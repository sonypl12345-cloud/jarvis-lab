const status = document.getElementById('status');
document.getElementById('capture').addEventListener('click', async () => {
  status.textContent = 'Reading active page…';
  try {
    const [tab] = await chrome.tabs.query({active:true,currentWindow:true});
    const [{result}] = await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>{
      if(!window.__jarvisDomState){
        window.__jarvisDomState={version:1,lastMutation:Date.now(),timer:null,url:location.href};
        window.__jarvisDomObserver=new MutationObserver(records=>{
          const significant=records.some(r=>r.type==='childList'?(r.addedNodes.length||r.removedNodes.length):['disabled','aria-disabled','role','contenteditable'].includes(r.attributeName));
          if(!significant)return;
          window.__jarvisDomState.version+=1;window.__jarvisDomState.lastMutation=Date.now();clearTimeout(window.__jarvisDomState.timer);
          window.__jarvisDomState.timer=setTimeout(()=>fetch('http://127.0.0.1:8790/invalidate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason:location.href!==window.__jarvisDomState.url?'url_change':'significant_dom_mutation'})}).catch(()=>{}),600);
        });
        window.__jarvisDomObserver.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['disabled','aria-disabled','role','contenteditable']});
      }
      const visible=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
      const selector='a[href],button,input,textarea,select,[role="button"],[role="link"],[role="textbox"],[contenteditable="true"]';
      const elements=[...document.querySelectorAll(selector)].filter(visible).slice(0,500).map((el,i)=>({id:`e${i+1}`,tag:el.tagName.toLowerCase(),role:el.getAttribute('role')||'',type:el.getAttribute('type')||'',name:(el.getAttribute('aria-label')||el.innerText||el.getAttribute('placeholder')||el.getAttribute('title')||'').trim().replace(/\s+/g,' ').slice(0,240),href:el.tagName==='A'?(el.getAttribute('href')||'').slice(0,500):'',disabled:!!el.disabled}));
      return{page:{title:document.title,url:location.href,lang:document.documentElement.lang||''},elements,dom_version:window.__jarvisDomState.version,settled_ms:Date.now()-window.__jarvisDomState.lastMutation};
    }});
    const response=await fetch('http://127.0.0.1:8790/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(result)});
    const saved=await response.json();status.textContent=saved.ok?`Saved ${saved.stored} elements. Snapshot ${saved.snapshot_id}; TTL ${saved.ttl_seconds}s.`:`Error: ${saved.error}`;
  }catch(error){status.textContent=`Error: ${error.message}`;}
});
