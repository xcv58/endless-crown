import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const themeSource = readFileSync(new URL('../dist/theme.js', import.meta.url), 'utf8');
const demoSource = readFileSync(new URL('../dist/demo.js', import.meta.url), 'utf8');
const key = 'endless-crown-appearance';

function events(properties = {}) {
  const listeners = {};
  return Object.assign(properties, {
    addEventListener(type, handler) { (listeners[type] ??= []).push(handler); },
    setAttribute(name, value) { (this.attributes ??= {})[name] = value; },
    async emit(type, event = {}) {
      for (const handler of listeners[type] ?? []) await handler(event);
    },
  });
}

function theme({ dark = false, saved = null, blocked = false } = {}) {
  const storage = new Map(saved === null ? [] : [[key, saved]]);
  const toggle = events({ hidden: true, dataset: {} });
  const reset = events({ hidden: true });
  const system = events({ matches: dark });
  const meta = {};
  const root = { dataset: {}, style: {} };
  let ready = false;
  const document = events({
    documentElement: root,
    querySelector: () => meta,
    querySelectorAll: (selector) => ready ? (selector === '[data-appearance]' ? [toggle] : [reset]) : [],
  });
  const window = events({ matchMedia: () => system });
  const guard = () => { if (blocked) throw new Error('Storage blocked'); };
  const localStorage = {
    getItem(k) { guard(); return storage.get(k) ?? null; },
    setItem(k, value) { guard(); storage.set(k, value); },
    removeItem(k) { guard(); storage.delete(k); },
  };
  vm.runInNewContext(themeSource, { document, window, localStorage });
  return {
    root, toggle, reset, system, storage, meta, window,
    async ready() { ready = true; await document.emit('DOMContentLoaded'); },
    async toggleTheme() { await toggle.emit('click'); },
    async followSystem() { await reset.emit('click'); },
  };
}

test('system appearance resolves before DOM readiness and follows system changes', async () => {
  const t = theme({ dark: true });
  assert.equal(t.root.dataset.theme, 'dark');
  assert.equal(t.meta.content, '#101211');
  await t.ready();
  assert.equal(t.reset.attributes['aria-disabled'], 'true');
  assert.equal(t.toggle.hidden, false);
  assert.equal(t.toggle.attributes['aria-label'], 'Switch to light mode');
  t.system.matches = false;
  await t.system.emit('change');
  assert.equal(t.root.dataset.theme, 'light');
  assert.equal(t.toggle.attributes['aria-label'], 'Switch to dark mode');
  assert.equal(t.root.style.colorScheme, 'light');
  assert.equal(t.storage.size, 0);
});

test('manual appearance survives navigation; System clears the override', async () => {
  const t = theme({ dark: true });
  await t.ready();
  await t.toggleTheme();
  assert.equal(t.storage.get(key), 'light');
  await t.system.emit('change');
  assert.equal(t.root.dataset.theme, 'light');
  const nextPage = theme({ dark: true, saved: t.storage.get(key) });
  await nextPage.ready();
  assert.equal(nextPage.toggle.attributes['aria-label'], 'Switch to dark mode');
  assert.equal(nextPage.reset.attributes['aria-disabled'], 'false');
  assert.equal(nextPage.root.dataset.theme, 'light');
  await nextPage.followSystem();
  assert.equal(nextPage.storage.has(key), false);
  assert.equal(nextPage.root.dataset.theme, 'dark');
});

test('blocked storage does not prevent switching; invalid preferences use the system', async () => {
  const t = theme({ blocked: true });
  await t.ready();
  await t.toggleTheme();
  assert.equal(t.root.dataset.theme, 'dark');
  assert.equal(t.storage.size, 0);
  assert.equal(theme({ saved: 'unexpected', dark: true }).root.dataset.theme, 'dark');
});

test('appearance synchronizes across tabs and responds to cleared storage', async () => {
  const t = theme();
  await t.ready();
  await t.window.emit('storage', { key, newValue: 'dark' });
  assert.equal(t.root.dataset.theme, 'dark');
  assert.equal(t.toggle.dataset.mode, 'dark');
  assert.equal(t.toggle.attributes['aria-label'], 'Switch to light mode');
  await t.window.emit('storage', { key: 'unrelated', newValue: 'light' });
  assert.equal(t.root.dataset.theme, 'dark');
  await t.window.emit('storage', { key: null, newValue: null });
  assert.equal(t.root.dataset.theme, 'light');
  assert.equal(t.reset.attributes['aria-disabled'], 'true');
});

function demo({ rejects = false } = {}) {
  const label = {};
  const button = events({ hidden: true, disabled: false, querySelector: () => label });
  const status = { textContent: '' };
  let calls = 0;
  const video = events({
    async play() {
      calls++;
      if (rejects) throw new Error('Playback unavailable');
      await video.emit('play');
      document.activeElement = null;
    },
    focus() { document.activeElement = video; },
  });
  const document = {
    activeElement: button,
    querySelector: (selector) => ({ '#demo-video': video, '#demo-play': button, '#demo-status': status })[selector],
  };
  vm.runInNewContext(demoSource, { document });
  return { video, button, status, label, document, calls: () => calls };
}

test('video waits for a click, preserves keyboard focus, and offers replay', async () => {
  const d = demo();
  assert.equal(d.calls(), 0);
  assert.equal(d.button.hidden, false);
  await d.button.emit('click');
  assert.equal(d.calls(), 1);
  assert.equal(d.button.hidden, true);
  assert.equal(d.document.activeElement, d.video);
  assert.equal(d.status.textContent, '');
  await d.video.emit('ended');
  assert.equal(d.button.hidden, false);
  assert.equal(d.label.textContent, 'Watch again · 27 sec');
});

test('failed playback permits retry and media errors explain the fallback', async () => {
  const d = demo({ rejects: true });
  await d.button.emit('click');
  assert.equal(d.button.hidden, false);
  assert.equal(d.button.disabled, false);
  assert.match(d.status.textContent, /could not play/);
  await d.video.emit('error');
  assert.equal(d.button.hidden, true);
  assert.match(d.status.textContent, /could not load/);
});
