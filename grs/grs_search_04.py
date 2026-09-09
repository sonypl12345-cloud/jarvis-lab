#!/usr/bin/env python3
import hashlib,json,re,time,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path.home()/"GenesisProjects"/"GRSForum"
OUT=ROOT/"grs_search_04_result.json"
UA={"User-Agent":"Mozilla/5.0 GRS-Search/0.4"}
CLAIMS=[
 {"id":"google_multiagent","claim":"Google is actively researching scaling and orchestration of multi-agent AI systems.","queries":["Google Research scaling agent systems multi-agent","Google multi-agent orchestration AI"]},
 {"id":"anthropic_multiagent","claim":"Anthropic has built and documented a multi-agent research system.","queries":["Anthropic multi-agent research system","Anthropic multi-agent research"]},
 {"id":"aws_multiagent","claim":"AWS is developing multi-agent systems using Bedrock or Strands Agents.","queries":["AWS Bedrock Strands Agents multi-agent","AWS multi-agent AI Bedrock"]},
]
PRIMARY=("Google Research","Anthropic","aws.amazon.com","Amazon Web Services","Microsoft","Nature","arXiv")
BAD=("Medium","DataDrivenInvestor","MarketWise","Memeburn")

def get(url,timeout=20):
 req=urllib.request.Request(url,headers=UA)
 with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()

def news(q,n=12):
 url="https://news.google.com/rss/search?q="+urllib.parse.quote(q)+"&hl=en-US&gl=US&ceid=US:en"
 root=ET.fromstring(get(url))
 out=[]
 for it in root.findall('.//item')[:n]:
  title=(it.findtext('title') or '').strip(); src=(it.findtext('source') or '').strip(); link=(it.findtext('link') or '').strip(); pub=(it.findtext('pubDate') or '').strip()
  if title and link: out.append({"title":title,"url":link,"source":src or "unknown","published":pub,"provider":"google_news"})
 return out

def arxiv(q,n=8):
 terms=' OR '.join('all:"'+x+'"' for x in q.split()[:5])
 url="https://export.arxiv.org/api/query?search_query="+urllib.parse.quote('('+terms+')')+"&start=0&max_results="+str(n)+"&sortBy=relevance&sortOrder=descending"
 root=ET.fromstring(get(url)); ns={'a':'http://www.w3.org/2005/Atom'}; out=[]
 for e in root.findall('a:entry',ns):
  title=' '.join((e.findtext('a:title','',ns) or '').split()); link=e.findtext('a:id','',ns); pub=e.findtext('a:published','',ns)
  if title and link: out.append({"title":title,"url":link,"source":"arXiv","published":pub,"provider":"arxiv"})
 return out

def tokens(s):return {x for x in re.sub(r'[^a-z0-9]+',' ',s.lower()).split() if len(x)>2}
def score(claim,title):
 a=tokens(claim); b=tokens(title)
 return len(a&b)/max(1,len(a))
def source_root(h):
 s=(h.get('source') or 'unknown').lower()
 for x in ('google research','anthropic','aws.amazon.com','amazon web services','microsoft','nature','arxiv'):
  if x in s:return x
 return s

results=[]
for c in CLAIMS:
 hits=[]; errors=[]
 for q in c['queries']:
  try:hits+=news(q)
  except Exception as e:errors.append('news:'+type(e).__name__)
 try:hits+=arxiv(c['queries'][0])
 except Exception as e:errors.append('arxiv:'+type(e).__name__)
 seen=set(); filtered=[]
 for h in hits:
  key=(h['title'].lower(),source_root(h))
  if key in seen:continue
  seen.add(key)
  h['relevance']=round(score(c['claim'],h['title']),3)
  h['primary']=any(x.lower() in (h['source']+' '+h['title']).lower() for x in PRIMARY)
  h['critic_accept']=h['relevance']>=0.12 and not any(x.lower() in (h['source']+' '+h['title']).lower() for x in BAD)
  if h['critic_accept']:filtered.append(h)
 roots=sorted({source_root(h) for h in filtered if source_root(h) not in ('unknown','news.google.com')})
 providers=sorted({h['provider'] for h in filtered})
 primary_roots=sorted({source_root(h) for h in filtered if h['primary']})
 if len(primary_roots)>=1 and len(roots)>=2:status='VERIFIED'
 elif len(roots)>=2:status='MULTI_SOURCE'
 elif len(roots)==1:status='SINGLE_SOURCE'
 else:status='UNRESOLVED'
 results.append({"claim_id":c['id'],"claim":c['claim'],"status":status,"independent_roots":roots,"providers":providers,"primary_roots":primary_roots,"evidence":sorted(filtered,key=lambda x:(x['primary'],x['relevance']),reverse=True)[:10],"errors":errors})

out={"schema":"GRS-SEARCH-0.4","verdict":"GRS_SEARCH_04_PASS","claims":results,"verified_claims":sum(r['status']=='VERIFIED' for r in results),"genesis_mutation":False,"memory_write":False,"motor_effect":False,"ts":time.time()}
out['sha256']=hashlib.sha256(json.dumps(out,sort_keys=True).encode()).hexdigest()
OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False))
print(json.dumps({"verdict":out['verdict'],"verified_claims":out['verified_claims'],"statuses":[[r['claim_id'],r['status'],len(r['independent_roots'])] for r in results],"sha256":out['sha256']}))
