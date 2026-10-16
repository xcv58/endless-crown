(() => {
function initializeHeaderMenu({ header, control, panel, breakpoint, label }) {
  if (!header || !control || !panel) return;
  const phone = window.matchMedia(`(max-width: ${breakpoint}px)`);
  let lastHeaderFocus = null;
  const isOpen = () => phone.matches && !panel.hidden;
  const setOpen = open => {
    panel.hidden = phone.matches && !open;
    control.setAttribute('aria-expanded', String(phone.matches && open));
    control.setAttribute('aria-label', label(phone.matches && open));
    control.title = control.getAttribute('aria-label');
    if (!open) panel.querySelectorAll('details[open]').forEach(details => { details.open = false; });
  };
  const close = (returnFocus = false) => {
    const wasOpen = isOpen();
    setOpen(false);
    if (wasOpen && returnFocus) control.focus({ preventScroll: true });
  };
  const sync = () => {
    // CSS may hide the focused link before the media-query event reaches us.
    const active = document.activeElement === document.body ? lastHeaderFocus : document.activeElement;
    const panelFocused = !!active && panel.contains(active);
    const menuFocused = active === control;
    control.hidden = !phone.matches;
    setOpen(false);
    // Match the visible reading order while retaining one set of native links.
    if (phone.matches) {
      if (header.lastElementChild !== panel) header.append(panel);
    } else if (panel.nextElementSibling !== control) header.insertBefore(panel, control);
    if (phone.matches && panelFocused) control.focus({ preventScroll: true });
    else if (!phone.matches && (panelFocused || menuFocused)) {
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
  phone.addEventListener('change', sync);
  window.addEventListener('pageshow', event => { if (event.persisted) sync(); });
  header.setAttribute('data-header-ready', '');
  sync();
}

initializeHeaderMenu({ header: document.querySelector('.site-header'), control: document.querySelector('.header-menu'), panel: document.querySelector('.header-navigation'), breakpoint: 700, label: open => open ? 'Close menu' : 'Open menu' });
})();
