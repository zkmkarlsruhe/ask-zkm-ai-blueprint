/* ============================================================================
 * carbon-badge.js — in-chat CO₂ widget for OpenWebUI
 * ----------------------------------------------------------------------------
 * Polls cost-tracker/'s public /api/carbon/{user_id} endpoint and renders a small
 * badge in the corner of the chat surface showing the user's CO₂ for today.
 *
 * This is a BLUEPRINT, not production code. To adapt for your install:
 *   1. Set CARBON_API to your cost-tracker's public carbon API URL.
 *   2. Set CARBON_PUBLIC_URL to your public carbon info page.
 *   3. Decide how you read the user's id (OWUI exposes user info in
 *      window.localStorage; the exact key may shift between versions).
 *   4. Adjust the inject target and styling to match your build of OWUI.
 *
 * Loaded into OpenWebUI by baking this file into the image — see
 * Dockerfile.example in this directory.
 * ========================================================================= */

(function () {
  'use strict';

  // ---- CONFIG (edit for your house) ----------------------------------------
  // Public host of cost-tracker/ (CARBON_DOMAIN), never the dashboard host.
  const CARBON_API = window.CARBON_API_BASE || 'https://carbon.example.org';
  const CARBON_PUBLIC_URL = window.CARBON_PUBLIC_URL || 'https://carbon.example.org/carbon';
  const POLL_INTERVAL_MS = 30_000;

  // ---- USER ID DISCOVERY ---------------------------------------------------
  // OWUI (0.9 through 0.12) keeps its session JWT in localStorage 'token'; the
  // payload carries the user id. Re-check this when you bump OWUI.
  function currentUserId() {
    try {
      const token = localStorage.getItem('token');
      if (!token) return null;
      const payload = token.split('.')[1];
      const json = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
      return json.id || json.sub || null;
    } catch {
      return null;
    }
  }

  // ---- BADGE DOM -----------------------------------------------------------
  function ensureBadge() {
    let badge = document.getElementById('co2-badge');
    if (badge) return badge;

    badge = document.createElement('a');
    badge.id = 'co2-badge';
    badge.href = CARBON_PUBLIC_URL;
    badge.target = '_blank';
    badge.rel = 'noopener';
    badge.title = 'Your estimated CO₂ today — click for details';
    Object.assign(badge.style, {
      position: 'fixed',
      bottom: '16px',
      right: '16px',
      padding: '6px 10px',
      background: 'rgba(39, 174, 96, 0.9)',
      color: 'white',
      borderRadius: '6px',
      fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
      fontSize: '12px',
      fontWeight: '600',
      textDecoration: 'none',
      zIndex: '9999',
      cursor: 'pointer',
      boxShadow: '0 2px 4px rgba(0,0,0,0.15)',
    });
    badge.textContent = '... g CO₂';
    document.body.appendChild(badge);
    return badge;
  }

  // ---- POLLER --------------------------------------------------------------
  async function refresh() {
    const userId = currentUserId();
    if (!userId) return;
    try {
      const r = await fetch(`${CARBON_API}/api/carbon/${encodeURIComponent(userId)}`, {
        method: 'GET',
        cache: 'no-store',
      });
      if (!r.ok) return;
      const { co2_kg } = await r.json();
      const grams = Math.round((co2_kg || 0) * 1000 * 100) / 100;
      const badge = ensureBadge();
      badge.textContent = `${grams.toFixed(2)} g CO₂`;
      // The public page shows the amount (in kg) when linked from the badge.
      badge.href = `${CARBON_PUBLIC_URL}?amount=${co2_kg || 0}`;
    } catch {
      /* network blip — try again next tick */
    }
  }

  function start() {
    refresh();
    setInterval(refresh, POLL_INTERVAL_MS);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
