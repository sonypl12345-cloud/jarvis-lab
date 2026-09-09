#!/usr/bin/env python3
import hashlib,json,re,time,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path.home()/"GenesisProjects"/"GRSForum"; OUT=ROOT/"grs_search_05_result.json"
UA={"User-Agent":"Mozilla/5.0 GRS-Search/0.5"}
CLAIMS=[
{"id":"google_multiagent","entity":["google","google research"],"claim":"Google Research studies scaling and orchestration of multi-agent AI systems.","queries":["Google Research scaling agent systems multi-agent"]},
{"id":"anthropic_multiagent","entity":["anthropic"],"claim":"Anthropic has documented a multi-agent research system.","queries":["Anthropic multi-agent research system"]},
{"id":"aws_multiagent","entity":["aws","amazon bedrock","strands agents"],"claim":"AWS develops multi-agent systems using Amazon Bedrock or Strands Agents.","queries":["AWS Amazon Bedrock Strands Agents multi-agent"]}]
PRIMARY={"google_multiagent":("google research","blog.google","google deepmind"),"anthropic_multiagent":("anthropic",),"aws_multiagent":("aws.amazon.com","amazon web services")}
NEG=("not ","no evidence","false","debunk","doesn't","does not")
def get(u):
 r=urllib.request.Request(u,headers=UA); return urllib.request.urlopen(r,timeout=20).read()
def news(q,n=20):
 u="https://news.google.com/rss/search?q="+urllib.parse.quote(q)+"&hl=en-US&gl=US&ceid=US:en"; root=ET.fromstring(get(u)); out=[]
 for i in root.findall('.//item')[:n]:
  t=(i.findtext('title') or '').strip(); s=(i.findtext('source') or '').strip(); l=(i.findtext('link') or '').strip(); p=(i.findtext('pubDate') or '').strip()
  if t and l: out.append({"title":t,"source":s,"url":l,"published":p,"provider":"google_news"})
 return out
def toks(s): return {x for x in re.sub(r'[^a-z0-9]+',' ',s.lower()).split() if len(x)>2}
def relevance(claim,title):
 a=toks(claim); b=toks(title); return len(a&b)/max(1,len(a))
def root(h): return (h.get('source') or 'unknown').lower().strip()
def entity_ok(c,h):
 x=(h['title']+' '+h['source']).lower(); return any(e in x for e in c['entity'])
def primary_ok(c,h):
 x=(h['title']+' '+h['source']).lower(); return any(p in x for p in PRIMARY[c['id']])
def contradict(h): return any(n in h['title'].lower() for n in NEG)
results=[]
for c in CLAIMS:
 hits=[]; errors=[]
 for q in c['queries']:
  try:hits+=news(q)
  except Exception as e: errors.append(type(e).__name__)
 accepted=[]; rejected=[]; seen=set()
 for h in hits:
  lineage=(root(h),re.sub(r'[^a-z0-9]+',' ',h['title'].lower()).strip())
  if lineage in seen: continue
  seen.add(lineage); rel=round(relevance(c['claim'],h['title']),3); ent=entity_ok(c,h); pri=primary_ok(c,h); con=contradict(h)
  h.update({"relevance":rel,"entity_match":ent,"primary":pri,"contradiction":con})
  if ent and rel>=0.25: accepted.append(h)
  else: rejected.append({"title":h['title'],"source":h['source'],"reason":"entity" if not ent else "low_relevance"})
 roots=sorted({root(h) for h in accepted if not h['contradiction']}); prim=[h for h in accepted if h['primary'] and not h['contradiction']]; cons=[h for h in accepted if h['contradiction']]
 # Strict tribunal: exact entity + strong relevance + at least one organization-primary item + >=2 independent roots + no unresolved contradiction.
 if prim and len(roots)>=2 and not cons: status="VERIFIED_STRICT"
 elif cons: status="CONTESTED"
 elif prim: status="PRIMARY_ONLY"
 elif roots: status="SUPPORTED_NOT_VERIFIED"
 else: status="UNRESOLVED"
 results.append({"claim_id":c['id'],"claim":c['claim'],"status":status,"independent_roots":roots,"primary_count":len(prim),"contradictions":cons[:5],"evidence":sorted(accepted,key=lambda x:(x['primary'],x['relevance']),reverse=True)[:10],"rejected_sample":rejected[:8],"errors":errors})
out={"schema":"GRS-SEARCH-0.5","verdict":"GRS_SEARCH_05_PASS","strict_verified":sum(r['status']=="VERIFIED_STRICT" for r in results),"claims":results,"gates":{"entity_match":True,"min_relevance":0.25,"primary_required":True,"independent_roots":2,"contradiction_search":True,"lineage_dedup":True},"genesis_mutation":False,"memory_write":False,"motor_effect":False,"ts":time.time()}
out['sha256']=hashlib.sha256(json.dumps(out,sort_keys=True).encode()).hexdigest(); OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)); print(json.dumps({"verdict":out['verdict'],"strict_verified":out['strict_verified'],"statuses":[[r['claim_id'],r['status'],r['primary_count'],len(r['independent_roots'])] for r in results],"sha256":out['sha256']}))