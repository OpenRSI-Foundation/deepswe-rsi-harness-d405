// Child-local HTTP transport only. All upstream authority remains in Judge.
const http = require('http');
const fs = require('fs');
const crypto = require('crypto');
const root = '/tmp/deepswe-relay';
fs.mkdirSync(root, {recursive: true, mode: 0o700});
http.createServer((req, res) => {
  const id = crypto.randomBytes(16).toString('hex');
  const dir = `${root}/${id}`;
  fs.mkdirSync(dir, {mode: 0o700});
  let data = [], size = 0, ended = false, seq = 0, headers = false;
  req.on('data', x => { size += x.length; if (size > 16*1024*1024) req.destroy(); else data.push(x); });
  req.on('end', () => {
    fs.writeFileSync(`${dir}/request.tmp`, JSON.stringify({method:req.method,path:req.url,headers:req.headers,body:Buffer.concat(data).toString('base64')}));
    fs.renameSync(`${dir}/request.tmp`, `${dir}/request.json`);
  });
  res.on('close', () => { if (!ended) fs.writeFileSync(`${dir}/cancel`, '1'); });
  const timer = setInterval(() => {
    try {
      if (!headers && fs.existsSync(`${dir}/headers.json`)) {
        const h = JSON.parse(fs.readFileSync(`${dir}/headers.json`));
        res.writeHead(h.status, h.headers); headers = true;
      }
      if (headers) {
        while (fs.existsSync(`${dir}/chunk-${seq}`)) {
          res.write(fs.readFileSync(`${dir}/chunk-${seq}`));
          fs.unlinkSync(`${dir}/chunk-${seq}`); seq++;
        }
        if (fs.existsSync(`${dir}/done.json`)) {
          const d = JSON.parse(fs.readFileSync(`${dir}/done.json`));
          if (seq === d.chunks) { ended = true; res.end(); clearInterval(timer); fs.writeFileSync(`${dir}/ack`, '1'); }
        }
      }
      if (res.destroyed) clearInterval(timer);
    } catch (e) { res.destroy(); clearInterval(timer); fs.writeFileSync(`${dir}/cancel`, '1'); }
  }, 20);
}).listen(18765, '127.0.0.1');
