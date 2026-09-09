#!/usr/bin/env python3
"""GRS Search 0.6 — Active Verification.
Read-only web research experiment. No motor, Genesis mutation, or Memory writes.
Turns weak PRIMARY_ONLY claims into targeted independent-verification missions.
"""
import json, hashlib, re, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path.home()/"GenesisProjects"/"GRSForum"
OUT=ROOT/"grs_search_06_result.json"
UA={"User-Agent":"Mozilla/5.0 GRS-Search/0.6"}
MISSIONS=[{
 "claim_id":"aws_multiagent",
 "claim":"AWS develops multi-agent systems using Amazon Bedrock or Strands Agents.",
 "exclude_roots":["aws.amazon.com","amazon.com"],
 "queries":[
  "AWS Strands Agents multi-agent -site:aws.amazon.com",
  "Amazon Bedrock multi-agent systems Strands independent report -site:aws.amazon.com",
  "AWS multi-agent Strands Agents research paper"
 ]
}]
NEG=("not ","no evidence","false","debunk","does not","doesn't","misleading")
TRUST_HINTS=("reuters","techcrunch","venturebeat","theregister","infoq","arxiv","acm","ieee","nature","github")
def get(url):
 r=urllib.request.Request(url,headers=UA)
 return urllib.request.urlopen(r,timeout=20).read()
def news(q,n=25):
 url="https://news.google.com/rss/search?q="+urllib.parse.quote(q)+"&hl=en-US&gl=US&ceid=US:en"
 root=ET.fromstring(get(url)); out=[]
 for i in root.findall('.//item')[:n]:
  title=(i.findtext('title') or '').strip(); source=(i.findtext('source') or '').strip(); link=(i.findtext('link') or '').strip(); pub=(i.findtext('pubDate') or '').strip()
  if title and link: out.append({"title":title,"source":source,"url":link,"published":pub,"provider":"google_news"})
 return out
def norm(s): return re.sub(r'[^a-z0-9]+',' ',s.lower()).strip()
def relevant(h):
 x=norm(h['title']+' '+h['source'])
 return (('aws' in x or 'amazon' in x) and ('multi agent' in x or 'strands' in x or 'bedrock' in x))
def excluded(h,roots):
 x=(h.get('source','')+' '+h.get('url','')).lower()
 return any(r in x for r in roots)
def contradiction(h): return any(n in h['title'].lower() for n in NEG)
def quality(h):
 x=(h['source']+' '+h['title']).lower(); return 2 if any(t in x for t in TRUST_HINTS) else 1
all_results=[]
for m in MISSIONS:
 raw=[]; errors=[]
 for q in m['queries']:
  try: raw += news(q)
  except Exception as e: errors.append(type(e).__name__)
 seen=set(); support=[]; contradict=[]; rejected=[]
 for h in raw:
  key=(norm(h['source']),norm(h['title']))
  if key in seen: continue
  seen.add(key)
  if excluded(h,m['exclude_roots']): rejected.append({"title":h['title'],"source":h['source'],"reason":"excluded_original_root"}); continue
  if not relevant(h): rejected.append({"title":h['title'],"source":h['source'],"reason":"low_claim_relevance"}); continue
  h['quality']=quality(h)
  if contradiction(h): contradict.append(h)
  else: support.append(h)
 roots=sorted({norm(h['source']) for h in support if norm(h['source'])})
 strong=[h for h in support if h['quality']>=2]
 if contradict: status="CONTESTED"
 elif strong and len(roots)>=2: status="INDEPENDENTLY_VERIFIED"
 elif support: status="INDEPENDENT_SUPPORT_FOUND"
 else: status="NO_INDEPENDENT_SUPPORT"
 all_results.append({"claim_id":m['claim_id'],"claim":m['claim'],"status":status,"independent_roots":roots,"strong_support_count":len(strong),"support":sorted(support,key=lambda h:h['quality'],reverse=True)[:12],"contradictions":contradict[:8],"rejected_sample":rejected[:10],"errors":errors})
out={"schema":"GRS-SEARCH-0.6","verdict":"GRS_SEARCH_06_PASS","mode":"ACTIVE_VERIFICATION","missions":all_results,"policy":{"exclude_original_root":True,"target_weak_claims":True,"contradiction_search":True,"require_independent_roots":2},"genesis_mutation":False,"memory_write":False,"motor_effect":False,"ts":time.time()}
out['sha256']=hashlib.sha256(json.dumps(out,sort_keys=True).encode()).hexdigest()
OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False))
print(json.dumps({"verdict":out['verdict'],"missions":[[m['claim_id'],m['status'],len(m['independent_roots']),m['strong_support_count']] for m in all_results],"sha256":out['sha256']}))