#!/bin/bash
set -euo pipefail
cd /workspace
exec /opt/pier/.venv/bin/python -I /tests/launch.py
