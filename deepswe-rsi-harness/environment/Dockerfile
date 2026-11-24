FROM node:22-bookworm AS node
FROM python:3.12-bookworm
RUN test "$(uname -m)" = x86_64 && apt-get update && apt-get install -y --no-install-recommends git ca-certificates curl ripgrep && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/ /usr/local/
RUN python3 -m pip install --no-cache-dir uv==0.9.5 && python3 -m venv /opt/harbor && /opt/harbor/bin/pip install --no-cache-dir harbor==0.21.0
COPY pier.tar.gz /opt/pier.tar.gz
RUN mkdir /opt/pier && tar -xzf /opt/pier.tar.gz -C /opt/pier && rm /opt/pier.tar.gz && cd /opt/pier && UV_LINK_MODE=copy uv sync --frozen --no-dev
RUN mkdir -p /opt/references/payload/bin && npm install --prefix /opt/references/payload --omit=dev @openai/codex@0.172.0 @anthropic-ai/claude-code@2.1.331 && cp /usr/local/bin/node /opt/references/payload/bin/node && cp /usr/bin/rg /opt/references/payload/bin/rg && ln -s ../node_modules/.bin/codex /opt/references/payload/bin/codex && ln -s ../node_modules/.bin/claude /opt/references/payload/bin/claude
COPY public/ /opt/deepswe/
COPY development.json /opt/deepswe/development.json
RUN cp /opt/deepswe/reference.py /opt/references/reference.py && cp /opt/deepswe/relay.js /opt/references/relay.js && cp /opt/deepswe/codex.json /opt/references/codex.json && cp /opt/deepswe/claude.json /opt/references/claude.json && ln -s /opt/deepswe/validate_candidate.py /usr/local/bin/validate-candidate && ln -s /opt/deepswe/research.py /usr/local/bin/research-fetch
ENV PYTHONDONTWRITEBYTECODE=1 HARBOR_TELEMETRY=0 UV_CACHE_DIR=/opt/uv-cache
WORKDIR /workspace
# Close the starting state after every installation and initialization step.
RUN rm -rf /workspace/* /workspace/.[!.]* /workspace/..?* && mkdir /workspace/candidate /workspace/research && cp /opt/deepswe/noop.json /workspace/candidate.json && test "$(find /workspace -mindepth 1 -maxdepth 1 | wc -l)" = 3
