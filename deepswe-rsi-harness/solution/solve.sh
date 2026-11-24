#!/bin/bash
set -euo pipefail
cd /workspace
rm -rf -- /workspace/candidate
mkdir /workspace/candidate
cp -a /opt/references/payload /workspace/candidate/payload
cp /opt/references/reference.py /workspace/candidate/reference.py
cp /opt/references/relay.js /workspace/candidate/relay.js
cp /opt/references/claude.json /workspace/candidate/comparator-claude.json
cp /opt/references/codex.json /workspace/candidate.json
chmod 755 /workspace/candidate/reference.py
