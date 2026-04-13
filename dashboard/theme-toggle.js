/* ═══════════════════════════════════════════════════════════════
   Theme toggle — shared across all dashboard pages.
   - Reads/writes ps_theme in localStorage
   - Auto-injects the sun/moon button into the first `.topbar-right`
     if no #themeToggle already exists on the page
   - Wires the click handler
   For FOUC prevention, also include this tiny inline script in <head>:
     <script>if(localStorage.getItem('ps_theme')==='light'){document.documentElement.setAttribute('data-theme','light');}</script>
   ═══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  const DARK_ICON  = '<path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4.22 1.78a1 1 0 011.42 1.42l-.71.7a1 1 0 11-1.41-1.41l.7-.71zM18 9a1 1 0 110 2h-1a1 1 0 110-2h1zm-1.78 5.78a1 1 0 010 1.42l-.7.7a1 1 0 11-1.42-1.41l.71-.71a1 1 0 011.41 0zM11 16a1 1 0 11-2 0v-1a1 1 0 112 0v1zm-5.78-.78a1 1 0 01-1.41 0l-.71-.7a1 1 0 011.41-1.42l.71.71a1 1 0 010 1.41zM4 10a1 1 0 110-2H3a1 1 0 110 2h1zm1.22-6.22a1 1 0 010 1.41l-.71.71A1 1 0 013.1 4.49l.7-.71a1 1 0 011.42 0zM10 6a4 4 0 100 8 4 4 0 000-8z"/>';
  const LIGHT_ICON = '<path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"/>';

  function mountButton() {
    let btn = document.getElementById('themeToggle');
    if (!btn) {
      const host = document.querySelector('.topbar-right');
      btn = document.createElement('button');
      btn.className = 'theme-toggle';
      btn.id = 'themeToggle';
      btn.title = 'Toggle light / dark mode';
      btn.setAttribute('aria-label', 'Toggle light/dark mode');
      btn.innerHTML = '<svg id="themeIcon" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"></svg>';
      if (host) {
        host.appendChild(btn);
      } else {
        // Fallback: floating top-right for pages with no topbar
        btn.style.cssText = 'position:fixed;top:18px;right:18px;z-index:9998;background:rgba(20,16,10,0.72);border:1px solid rgba(201,168,76,0.35);color:#c9a84c;width:36px;height:36px;border-radius:8px;display:inline-flex;align-items:center;justify-content:center;cursor:pointer;backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);';
        const svg = btn.querySelector('svg');
        if (svg) { svg.style.width = '18px'; svg.style.height = '18px'; svg.setAttribute('fill', 'currentColor'); }
        (document.body || document.documentElement).appendChild(btn);
      }
    }
    const icon = btn.querySelector('#themeIcon') || document.getElementById('themeIcon');
    const isLightNow = document.documentElement.getAttribute('data-theme') === 'light';
    if (icon && !icon.innerHTML.trim()) {
      icon.innerHTML = isLightNow ? LIGHT_ICON : DARK_ICON;
    } else if (icon && isLightNow) {
      icon.innerHTML = LIGHT_ICON;
    }

    btn.addEventListener('click', function () {
      const isLight = document.documentElement.getAttribute('data-theme') === 'light';
      if (isLight) {
        document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('ps_theme', 'dark');
        if (icon) icon.innerHTML = DARK_ICON;
      } else {
        document.documentElement.setAttribute('data-theme', 'light');
        localStorage.setItem('ps_theme', 'light');
        if (icon) icon.innerHTML = LIGHT_ICON;
      }
    });
    return btn;
  }

  // Respect saved preference (redundant with the head boot script — belt + suspenders)
  if (localStorage.getItem('ps_theme') === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mountButton, { once: true });
  } else {
    mountButton();
  }
})();
