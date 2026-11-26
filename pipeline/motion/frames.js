// Render scenes.html frame by frame (pure function of time) into JPEGs.
// node frames.js timeline.json outdir fps [w h]
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const [tlPath, out, fpsS, wS, hS] = process.argv.slice(2);
  const fps = +fpsS || 30, w = +wS || 1080, h = +hS || 1920;
  const tl = JSON.parse(fs.readFileSync(tlPath, 'utf8'));
  fs.mkdirSync(out, { recursive: true });
  const exe = fs.existsSync('/opt/pw-browsers/chromium') ? undefined : undefined;
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: w, height: h } });
  await p.goto('file://' + path.resolve(__dirname, 'scenes.html') + `?w=${w}&h=${h}`);
  await p.evaluate(t => window.setTimeline(t), tl);
  const n = Math.ceil(tl.total * fps); const t0 = Date.now();
  for (let i = 0; i < n; i++) {
    const url = await p.evaluate(t => window.frameData(t), i / fps);
    fs.writeFileSync(path.join(out, `f${String(i).padStart(5, '0')}.jpg`), Buffer.from(url.split(',')[1], 'base64'));
    if (i % 150 === 0) console.log(`frame ${i}/${n}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  await b.close();
})();
