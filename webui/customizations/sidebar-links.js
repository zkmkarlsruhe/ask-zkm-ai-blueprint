/* ============================================================================
 * sidebar-links.js — append house-specific links to the OpenWebUI sidebar
 * ----------------------------------------------------------------------------
 * Adds links like "Privacy notice", "House documentation", "Report a problem"
 * to the bottom of the OWUI left sidebar. Survives client-side route changes.
 *
 * This is a BLUEPRINT. The DOM selectors below match a specific OWUI build —
 * inspect your version's sidebar markup and adjust SIDEBAR_SELECTOR if needed.
 * ========================================================================= */

(function () {
  'use strict';

  // ---- CONFIG (edit for your house) ----------------------------------------
  const LINKS = [
    { href: '/docs', label: 'Documentation' },
    { href: '/privacy', label: 'Privacy notice' },
    { href: 'mailto:ai-support@zkm.tech', label: 'Report a problem' },
  ];
  const SIDEBAR_SELECTOR = 'aside, nav[role="navigation"], [data-sidebar]';
  const CONTAINER_ID = 'house-sidebar-links';

  function buildContainer() {
    const wrap = document.createElement('div');
    wrap.id = CONTAINER_ID;
    Object.assign(wrap.style, {
      padding: '12px 16px',
      borderTop: '1px solid rgba(255,255,255,0.1)',
      marginTop: 'auto',
      fontSize: '12px',
    });
    LINKS.forEach(({ href, label }) => {
      const a = document.createElement('a');
      a.href = href;
      a.textContent = label;
      a.target = href.startsWith('http') ? '_blank' : '_self';
      a.rel = 'noopener';
      Object.assign(a.style, {
        display: 'block',
        padding: '4px 0',
        color: 'inherit',
        opacity: '0.7',
        textDecoration: 'none',
      });
      wrap.appendChild(a);
    });
    return wrap;
  }

  function inject() {
    if (document.getElementById(CONTAINER_ID)) return;
    const sidebar = document.querySelector(SIDEBAR_SELECTOR);
    if (!sidebar) return;
    sidebar.appendChild(buildContainer());
  }

  // OWUI is a SPA: re-inject on DOM changes that may have replaced the sidebar.
  const observer = new MutationObserver(() => inject());
  observer.observe(document.body, { childList: true, subtree: true });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inject);
  } else {
    inject();
  }
})();
