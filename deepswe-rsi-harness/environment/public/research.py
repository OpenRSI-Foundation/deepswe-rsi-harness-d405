#!/usr/local/bin/python3 -I
"""Explicit public research through the operator's logged provider route."""
import argparse
import json
import os
import urllib.request

ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True)
g.add_argument('--url');g.add_argument('--query');g.add_argument('--development-images',action='store_true');a=ap.parse_args()
base=os.environ.get('OPENAI_BASE_URL') or os.environ.get('ANTHROPIC_BASE_URL') or os.environ.get('RSI_AGENT_API_BASE_URL')
key=os.environ.get('OPENAI_API_KEY') or os.environ.get('ANTHROPIC_API_KEY')
if not base or not key:raise SystemExit('The operator broker provider route is required.')
base=base.rstrip('/').removesuffix('/v1')
op='development-images' if a.development_images else 'fetch' if a.url else 'search'
body={} if a.development_images else {'url':a.url} if a.url else {'query':a.query}
request=urllib.request.Request(base+'/research/'+op,data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=120) as response:print(response.read().decode())
