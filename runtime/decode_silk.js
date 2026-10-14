const fs = require('fs');
const { decode } = require('silk-wasm');

(async () => {
  const src = process.argv[2];
  const sr = parseInt(process.argv[3] || '24000', 10);
  const buf = fs.readFileSync(src);
  const r = await decode(buf, sr);
  fs.writeFileSync(src + '.pcm', Buffer.from(r.data));
})().catch((e) => {
  console.error(String(e));
  process.exit(1);
});
