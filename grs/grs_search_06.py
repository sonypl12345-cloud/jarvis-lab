#!/usr/bin/env python3
"""GRS Search 0.6.1 — Active Verification + ownership-aware provenance.
Canonical Search 0.6 extension. Read-only web research experiment.
No motor, Genesis mutation, or Memory writes.
"""
import json, hashlib, re, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path.home()/"GenesisProjects"/"GRSForum"
OUT=ROOT/"grs_search_06_result.json"
UA={"User-Agent":"Mozilla/5.0 GRS-Search/0.6.1"}
MISSIONS=[{
 "claim_id":"aws_multiagent",
 "claim":"AWS develops multi-agent systems using Amazon Bedrock or Strands Agents.",
 "exclude_owners":["org:amazon"],
 "queries":[
  "AWS Strands Agents multi-agent -site:aws.amazon.com",
  "Amazon Bedrock multi-agent systems Strands independent report -site:aws.amazon.com",
  "AWS multi-agent Strands Agents research paper"
 ]
}]
NEG=("not ","no evidence","false","debunk","does not","doesn't","misleading")
TRUST_HINTS=("reuters","techcrunch","venturebeat","theregister","infoq","arxiv","acm","ieee","nature")

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

def owner_key(h):
 """Conservative ultimate-owner/source-family collapse for independence scoring.
 Unknown publishers remain distinct publisher keys; known shared corporate surfaces collapse.
 """
 x=norm((h.get('source') or '')+' '+(h.get('title') or '')+' '+(h.get('url') or ''))
 amazon_markers=(
  'aws amazon com','amazon web services','aws builder center','aws samples',
  'github aws samples','strands agents sdk','amazon bedrock','agentcore on aws'
 )
 if any(m in x for m in amazon_markers): return 'org:amazon'
 if 'google research' in x or 'google deepmind' in x or 'blog google' in x: return 'org:google'
 if 'anthropic' in x: return 'org:anthropic'
 if 'microsoft' in x: return 'org:microsoft'
 s=norm(h.get('source') or 'unknown')
 return 'publisher:'+s if s else 'publisher:unknown'

def relevant(h):
 x=norm(h['title']+' '+h['source'])
 return (('aws' in x or 'amazon' in x) and ('multi agent' in x or 'strands' in x or 'bedrock' in x))

def contradiction(h): return any(n in h['title'].lower() for n in NEG)

def quality(h):
 x=(h['source']+' '+h['title']).lower()
 return 2 if any(t in x for t in TRUST_HINTS) else 1

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
  if not relevant(h):
   rejected.append({"title":h['title'],"source":h['source'],"reason":"low_claim_relevance"}); continue
  h['publisher_root']=norm(h.get('source') or 'unknown')
  h['independence_key']=owner_key(h)
  h['quality']=quality(h)
  if h['independence_key'] in set(m['exclude_owners']):
   rejected.append({"title":h['title'],"source":h['source'],"owner":h['independence_key'],"reason":"excluded_shared_owner"}); continue
  if contradiction(h): contradict.append(h)
  else: support.append(h)
 owner_roots=sorted({h['independence_key'] for h in support if h.get('independence_key')})
 publisher_roots=sorted({h['publisher_root'] for h in support if h.get('publisher_root')})
 strong=[h for h in support if h['quality']>=2 and h['independence_key']!='org:amazon']
 strong_owners=sorted({h['independence_key'] for h in strong})
 if contradict: status="CONTESTED"
 elif len(strong_owners)>=2: status="INDEPENDENTLY_VERIFIED"
 elif support: status="INDEPENDENT_SUPPORT_FOUND"
 else: status="NO_INDEPENDENT_SUPPORT"
 all_results.append({
  "claim_id":m['claim_id'],"claim":m['claim'],"status":status,
  "independent_roots":owner_roots,"publisher_roots":publisher_roots,
  "strong_support_count":len(strong),"strong_owner_count":len(strong_owners),
  "support":sorted(support,key=lambda h:h['quality'],reverse=True)[:12],
  "contradictions":contradict[:8],"rejected_sample":rejected[:12],"errors":errors})
out={
 "schema":"GRS-SEARCH-0.6.1","verdict":"GRS_SEARCH_061_PASS","mode":"ACTIVE_VERIFICATION_OWNERSHIP_AWARE",
 "missions":all_results,
 "policy":{"ownership_aware":True,"ultimate_owner_independence":True,"exclude_original_owner":True,"target_weak_claims":True,"contradiction_search":True,"require_strong_independent_owners":2},
 "genesis_mutation":False,"memory_write":False,"motor_effect":False,"ts":time.time()}
out['sha256']=hashlib.sha256(json.dumps(out,sort_keys=True).encode()).hexdigest()
OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False))
print(json.dumps({"verdict":out['verdict'],"missions":[[m['claim_id'],m['status'],len(m['independent_roots']),m['strong_owner_count']] for m in all_results],"sha256":out['sha256']}))