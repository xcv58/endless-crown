(() => {
function initializeHeaderMenu({ header, control, panel, breakpoint, label }) {
  if (!header || !control || !panel) return;
  const phone = window.matchMedia(`(max-width: ${breakpoint}px)`);
  let lastHeaderFocus = null;
  let compact = false;
  let initialized = false;
  const desktopFits = () => {
    const brand = header.querySelector('.brand, .logo');
    const appearance = header.querySelector('.theme-toggle');
    if (!brand || !appearance) return true;
    header.setAttribute('data-menu-measuring', '');
    try {
      const style = getComputedStyle(header);
      const available = header.getBoundingClientRect().width - parseFloat(style.paddingLeft || 0) - parseFloat(style.paddingRight || 0);
      const needed = brand.getBoundingClientRect().width + panel.getBoundingClientRect().width + appearance.getBoundingClientRect().width + (parseFloat(style.columnGap) || 0) * 2;
      return needed <= available;
    } finally {
      header.removeAttribute('data-menu-measuring');
    }
  };
  const isOpen = () => compact && !panel.hidden;
  const setOpen = open => {
    panel.hidden = compact && !open;
    control.setAttribute('aria-expanded', String(compact && open));
    control.setAttribute('aria-label', label(compact && open));
    control.title = control.getAttribute('aria-label');
    if (!open) panel.querySelectorAll('details[open]').forEach(details => { details.open = false; });
  };
  const close = (returnFocus = false) => {
    const wasOpen = isOpen();
    setOpen(false);
    if (wasOpen && returnFocus) control.focus({ preventScroll: true });
  };
  const sync = (reset = false) => {
    const nextCompact = phone.matches || !desktopFits();
    if (initialized && compact === nextCompact && !reset) return;
    // CSS may hide the focused link before the media-query event reaches us.
    const active = document.activeElement === document.body ? lastHeaderFocus : document.activeElement;
    const panelFocused = !!active && panel.contains(active);
    const menuFocused = active === control;
    compact = nextCompact;
    initialized = true;
    header.toggleAttribute('data-menu-compact', compact);
    control.hidden = !compact;
    setOpen(false);
    // Match the visible reading order while retaining one set of native links.
    if (compact) {
      if (header.lastElementChild !== panel) header.append(panel);
    } else if (panel.nextElementSibling !== control) header.insertBefore(panel, control);
    if (compact && panelFocused) control.focus({ preventScroll: true });
    else if (!compact && (panelFocused || menuFocused)) {
      const destination = panelFocused ? active : panel.querySelector('a, summary, select, button');
      destination?.focus({ preventScroll: true });
    }
  };
  header.addEventListener('focusin', event => { lastHeaderFocus = event.target; });
  document.addEventListener('focusin', event => {
    if (!header.contains(event.target)) { lastHeaderFocus = null; close(); }
  });
  document.addEventListener('pointerdown', event => {
    if (!header.contains(event.target)) { lastHeaderFocus = null; close(); }
  }, true);
  control.addEventListener('click', () => setOpen(!isOpen()));
  document.addEventListener('click', event => {
    if (!header.contains(event.target)) close();
  });
  header.addEventListener('focusout', event => {
    if (event.relatedTarget && !header.contains(event.relatedTarget)) close();
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape' || !isOpen()) return;
    // Let the existing language disclosure handle its own first Escape.
    if (event.target.closest?.('details[open]')) return;
    event.preventDefault();
    close(true);
  }, true);
  panel.addEventListener('click', event => {
    const link = event.target.closest('a');
    if (!link || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return;
    close();
    const target = new URL(link.href);
    if (target.origin === location.origin && target.pathname === location.pathname && target.search === location.search && target.hash) {
      const destination = document.getElementById(decodeURIComponent(target.hash.slice(1)));
      if (destination) {
        destination.tabIndex = -1;
        destination.focus({ preventScroll: true });
      }
    }
  });
  let pendingSync = null;
  const scheduleSync = () => {
    if (pendingSync !== null) return;
    pendingSync = requestAnimationFrame(() => { pendingSync = null; sync(); });
  };
  phone.addEventListener('change', scheduleSync);
  window.addEventListener('resize', scheduleSync);
  document.fonts?.ready.then(scheduleSync);
  if (window.ResizeObserver) {
    const observer = new ResizeObserver(scheduleSync);
    [header, ...header.querySelectorAll('.brand, .logo, nav, summary')].forEach(element => observer.observe(element));
  }
  window.addEventListener('pageshow', event => { if (event.persisted) sync(true); });
  header.setAttribute('data-header-ready', '');
  sync();
}

initializeHeaderMenu({ header: document.querySelector('.site-header'), control: document.querySelector('.header-menu'), panel: document.querySelector('.header-navigation'), breakpoint: 700, label: open => open ? 'Close menu' : 'Open menu' });
})();
