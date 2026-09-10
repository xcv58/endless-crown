// Resolve the saved appearance before the stylesheet paints the page.
(() => {
  const key = 'endless-crown-appearance';
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  const normalize = (value) => ['light', 'dark'].includes(value) ? value : 'system';
  let preference = 'system';
  try { preference = normalize(localStorage.getItem(key)); } catch {}
  const resolved = () => preference === 'system' ? (system.matches ? 'dark' : 'light') : preference;

  function apply() {
    const theme = resolved();
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    const color = document.querySelector('meta[name="theme-color"]');
    if (color) color.content = theme === 'dark' ? '#101211' : '#f5f6f4';
    document.querySelectorAll('[data-appearance]').forEach((button) => {
      const label = theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
      button.dataset.mode = theme;
      button.setAttribute('aria-label', label);
      button.title = label;
      button.hidden = false;
    });
    document.querySelectorAll('[data-appearance-reset]').forEach((button) => {
      button.setAttribute('aria-disabled', String(preference === 'system'));
      button.title = preference === 'system' ? 'Following your system appearance' : 'Follow your system appearance';
      button.hidden = false;
    });
  }

  function choose(value) {
    preference = value;
    try {
      if (preference === 'system') localStorage.removeItem(key);
      else localStorage.setItem(key, preference);
    } catch {}
    apply();
  }

  apply();
  system.addEventListener('change', apply);
  window.addEventListener('storage', (event) => {
    if (event.key !== key && event.key !== null) return;
    preference = normalize(event.newValue);
    apply();
  });
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-appearance]').forEach((button) => {
      button.addEventListener('click', () => choose(resolved() === 'dark' ? 'light' : 'dark'));
    });
    document.querySelectorAll('[data-appearance-reset]').forEach((button) => {
      button.addEventListener('click', () => choose('system'));
    });
    apply();
  });
})();
