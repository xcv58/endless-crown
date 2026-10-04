import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import crypto from 'node:crypto';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const kit = path.dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(await fs.readFile(path.join(kit, 'manifest.json'), 'utf8'));
const template = await fs.readFile(path.join(kit, 'template.html'), 'utf8');
const output = path.join(kit, manifest.locale);
await fs.mkdir(output, { recursive: true });
await fs.mkdir(path.join(kit, 'variants'), { recursive: true });
const escape = (value) => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
const sha256 = (data) => crypto.createHash('sha256').update(data).digest('hex');
const browser = await chromium.launch({ headless: true, executablePath: process.env.SCREENSHOT_CHROMIUM_PATH || chromium.executablePath() });
const page = await browser.newPage({ viewport: { width: manifest.width, height: manifest.height }, deviceScaleFactor: 1, colorScheme: 'dark' });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const report = { renderer: 'Playwright Chromium', viewport: [manifest.width, manifest.height], locale: manifest.locale, sourceUI: 'proportionally fitted complete authentic captures', slides: [] };
try {
  for (const slide of manifest.slides) {
    const image = await fs.readFile(path.resolve(kit, slide.source));
    const presentation = slide.presentation || 'flat';
    let bezelImage;
    if (presentation === 'watch-hero') {
      bezelImage = await fs.readFile(path.join(kit, manifest.deviceArtwork.file));
      if (sha256(bezelImage) !== manifest.deviceArtwork.sha256) throw new Error('Official Watch artwork differs from the recorded source');
    }
    const capture = `<img class="capture" src="data:image/jpeg;base64,${image.toString('base64')}" alt="${escape(slide.alt)}">`;
    const bezel = bezelImage ? `<img class="bezel" src="data:image/png;base64,${bezelImage.toString('base64')}" alt="Official Apple Watch Series 11 bezel">` : '';
    const media = bezelImage ? `<div class="device">${capture}${bezel}</div>` : capture;
    const html = template.replaceAll('{{HEADLINE}}', escape(slide.headline)).replaceAll('{{DESCRIPTION}}', escape(slide.description)).replaceAll('{{ALT}}', escape(slide.alt)).replace('{{PRESENTATION}}', presentation).replace('{{MEDIA}}', media);
    await page.setContent(html);
    await page.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map(img => img.decode())); });
    const metrics = await page.evaluate(() => {
      const bounds = el => { const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }; };
      const textBounds = el => { const range = document.createRange(); range.selectNodeContents(el); return bounds(range); };
      return { canvas: bounds(document.querySelector('.card')), copy: bounds(document.querySelector('.copy')), headline: textBounds(document.querySelector('h1')), description: textBounds(document.querySelector('p')), image: bounds(document.querySelector('.capture')), naturalImage: [document.images[0].naturalWidth, document.images[0].naturalHeight], device: document.querySelector('.device') ? bounds(document.querySelector('.device')) : null, bezel: document.querySelector('.bezel') ? bounds(document.querySelector('.bezel')) : null, naturalBezel: document.querySelector('.bezel') ? [document.querySelector('.bezel').naturalWidth, document.querySelector('.bezel').naturalHeight] : null };
    });
    for (const key of ['headline', 'description', 'image']) {
      const r = metrics[key];
      if (r.x < 0 || r.y < 0 || r.x + r.width > manifest.width + .01 || r.y + r.height > manifest.height + .01) throw new Error(`${slide.id}: ${key} clips outside the canvas`);
    }
    if (metrics.description.y + metrics.description.height + 4 > (metrics.device || metrics.image).y) throw new Error(`${slide.id}: copy overlaps the capture`);
    if (Math.abs(metrics.image.width / metrics.image.height - metrics.naturalImage[0] / metrics.naturalImage[1]) > .0001) throw new Error(`${slide.id}: capture is distorted`);
    if (metrics.device) {
      const d = metrics.device;
      if (d.x < 0 || d.y < 0 || d.x + d.width > manifest.width || d.y + d.height > manifest.height) throw new Error('Watch artwork clips outside the canvas');
      if (Math.abs(d.width / d.height - metrics.naturalBezel[0] / metrics.naturalBezel[1]) > .0001) throw new Error('Watch artwork is distorted');
      const scale = d.width / manifest.deviceArtwork.naturalSize[0];
      const screen = manifest.deviceArtwork.screenRect;
      for (const [key, target] of Object.entries({ x: d.x + screen.x * scale, y: d.y + screen.y * scale, width: screen.width * scale, height: screen.height * scale })) {
        if (Math.abs(metrics.image[key] - target) > .01) throw new Error(`Capture does not match official screen aperture: ${key}`);
      }
    }
    const name = `${String(slide.order).padStart(2, '0')}-${slide.id}.png`;
    const rendered = await page.screenshot({ path: path.join(output, name), type: 'png', omitBackground: false, animations: 'disabled' });
    report.slides.push({ order: slide.order, filename: `${manifest.locale}/${name}`, headline: slide.headline, description: slide.description, presentation, bezelSha256: bezelImage ? sha256(bezelImage) : null, source: slide.source, sourceSha256: sha256(image), exportSha256: sha256(rendered), metrics });
    console.log(`Rendered ${name}`);
    if (presentation === 'watch-hero') {
      // Comparison uses identical copy and app content to isolate the frame choice.
      const flat = html.replace('card watch-hero', 'card watch-hero flat-comparison').replace(`<div class="device">${capture}${bezel}</div>`, capture);
      await page.setContent(flat);
      await page.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map(img => img.decode())); });
      await page.screenshot({ path: path.join(kit, 'variants/01-spin-flat.png'), type: 'png', omitBackground: false, animations: 'disabled' });
    }
  }
  const galleryItems = manifest.slides.map(slide => `<figure><img src="${manifest.locale}/${String(slide.order).padStart(2, '0')}-${slide.id}.png" alt="${escape(slide.alt)}"><figcaption>${String(slide.order).padStart(2, '0')} · ${escape(slide.headline)}</figcaption></figure>`).join('');
  const gallery = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Endless Crown — App Store screenshots</title><style>*{box-sizing:border-box}body{margin:0;background:#eef0eb;color:#263028;font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif;padding:32px}h1{margin:0 0 8px;font-size:28px;letter-spacing:-.7px}p{margin:0 0 24px;color:#596258;font-size:16px}.gallery{display:grid;grid-template-columns:repeat(3,416px);gap:24px;width:max-content}figure{margin:0}img{display:block;width:416px;height:496px}figcaption{font-size:14px;font-weight:550;padding-top:10px}a{color:inherit}.help{margin-top:24px}@media(max-width:1390px){.gallery{grid-template-columns:repeat(2,416px)}}@media(max-width:920px){body{padding:20px}.gallery{grid-template-columns:1fr;width:100%;max-width:416px}.gallery img{width:100%;height:auto}}</style><header><h1>Endless Crown</h1><p>1.0.1 · English (U.S.) · Apple Watch · 416 × 496 px · upload in this order</p></header><main class="gallery">${galleryItems}</main><p class="help">The first image uses official Apple Watch hardware artwork. Feature screens stay large. Captures are complete and proportionate; headlines stay outside the app UI. <a href="README.md">Read the material notes</a>.</p></html>`;
  await fs.writeFile(path.join(kit, 'preview.html'), gallery);
  await page.setViewportSize({ width: 1360, height: 1254 });
  await page.goto(`file://${path.join(kit, 'preview.html')}`);
  await page.addStyleTag({ content: '.gallery { grid-template-columns: repeat(3, 416px) !important; } .help { display: none; }' });
  await page.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map(img => img.decode())); });
  await page.screenshot({ path: path.join(kit, 'contact-sheet.png'), type: 'png', omitBackground: false, fullPage: true });
  const comparison = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Endless Crown — first screenshot comparison</title><style>*{box-sizing:border-box}body{margin:0;padding:28px;background:#eef0eb;color:#263028;font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif}h1{font-size:26px;letter-spacing:-.7px;margin:0 0 8px}p{font-size:16px;color:#596258;margin:0 0 24px}.compare{display:flex;gap:24px}figure{margin:0;width:416px}figcaption{font-size:15px;font-weight:600;margin:0 0 10px}img{display:block;width:416px;height:496px}@media(max-width:900px){.compare{flex-direction:column}figure{width:100%;max-width:416px}img{width:100%;height:auto}}</style><h1>Show the interaction. Keep the features readable.</h1><p>Same headline and real app capture. The Watch bezel is used on the first image only.</p><main class="compare"><figure><figcaption>Feature wrapper</figcaption><img src="variants/01-spin-flat.png" alt="First screenshot without hardware artwork"></figure><figure><figcaption>Feature wrapper + official Watch bezel</figcaption><img src="en-US/01-spin.png" alt="First screenshot with official Apple Watch artwork"></figure></main></html>`;
  await fs.writeFile(path.join(kit, 'comparison.html'), comparison);
  await page.setViewportSize({ width: 920, height: 638 });
  await page.goto(`file://${path.join(kit, 'comparison.html')}`);
  await page.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map(img => img.decode())); });
  await page.screenshot({ path: path.join(kit, 'comparison.png'), type: 'png', omitBackground: false, fullPage: true });
  await page.setViewportSize({ width: 624, height: 690 });
  await page.goto(`file://${path.join(kit, 'preview.html')}`);
  await page.addStyleTag({ content: 'body{padding:22px}.gallery{grid-template-columns:repeat(3,180px)!important;gap:20px;width:max-content;max-width:none}.gallery img{width:180px!important;height:auto}h1{font-size:24px}header p{font-size:13px;margin-bottom:20px}figcaption{font-size:12px}.help{display:none}' });
  await page.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map(img => img.decode())); });
  await page.screenshot({ path: path.join(kit, 'thumbnail-check.png'), type: 'png', omitBackground: false, fullPage: true });
  const previewCheck = { browserVersion: browser.version(), mobile: [], pageErrors: errors };
  for (const name of ['preview.html', 'comparison.html']) {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`file://${path.join(kit, name)}`);
    await page.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map(img => img.decode())); });
    const result = await page.evaluate(() => ({ viewport: innerWidth, documentWidth: document.documentElement.scrollWidth, images: document.images.length, complete: [...document.images].every(img => img.complete && img.naturalWidth > 0) }));
    if (result.documentWidth > result.viewport || !result.complete) throw new Error(`${name}: mobile preview failed`);
    previewCheck.mobile.push({ file: name, ...result });
  }
  await fs.writeFile(path.join(kit, 'preview-check.json'), JSON.stringify(previewCheck, null, 2) + '\n');
  report.pageErrors = errors;
  if (errors.length) throw new Error(errors.join('\n'));
  await fs.writeFile(path.join(kit, 'render-report.json'), JSON.stringify(report, null, 2) + '\n');
} finally {
  await browser.close();
}
