/* ClimaClue: Google Analytics 4 with Google consent mode, and the cookie choice for visitors in Europe (24 Nov 2026).
 *
 * - Analytics cookies are off by default in the EEA, the UK and Switzerland (Google applies the region by IP address) and
 *   on elsewhere. Advertising cookies are off everywhere (no ads yet).
 * - The banner shows only to visitors whose time zone is in Europe and who haven't chosen yet; the choice is kept in
 *   this browser (localStorage) and can be changed from the Privacy page (any element with data-cookie-settings).
 * - Google's script loads after the page has finished loading and the browser is idle, so it never slows the first view.
 * - Nothing loads off climaclue.com (local previews and tests) or inside the embeddable chart.
 */
(function () {
  var ID = 'G-3YBNHQBFFM', KEY = 'climaclue.consent.v1';
  var live = /(^|\.)climaclue\.com$/.test(location.hostname) && !/^\/embed\//.test(location.pathname);
  var EUROPE = ['AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IE','IT','LV','LT','LU','MT','NL','PL','PT','RO','SK','SI','ES','SE','IS','LI','NO','GB','CH'];
  function stored() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function remember(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }

  window.dataLayer = window.dataLayer || [];
  function gtag() { dataLayer.push(arguments); }
  window.gtag = window.gtag || gtag;
  var off = { analytics_storage: 'denied', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied' };
  gtag('consent', 'default', { analytics_storage: 'denied', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied', region: EUROPE, wait_for_update: 500 });
  gtag('consent', 'default', { analytics_storage: 'granted', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied' });
  var choice = stored();
  if (choice === 'yes') gtag('consent', 'update', { analytics_storage: 'granted' });
  if (choice === 'no') gtag('consent', 'update', off);
  gtag('js', new Date());
  gtag('config', ID);

  if (live) {
    var start = function () {
      var go = function () { var s = document.createElement('script'); s.async = true; s.src = 'https://www.googletagmanager.com/gtag/js?id=' + ID; document.head.appendChild(s); };
      setTimeout(function () { window.requestIdleCallback ? requestIdleCallback(go, { timeout: 4000 }) : go(); }, 1500);
    };
    document.readyState === 'complete' ? start() : addEventListener('load', start);
  }

  var tz = ''; try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (e) {}
  var european = /^Europe\//.test(tz) || /^Atlantic\/(Canary|Madeira|Azores|Reykjavik|Faroe)$/.test(tz) || tz === 'Arctic/Longyearbyen';

  function banner() {
    if (document.getElementById('cc-consent')) return;
    var css = document.createElement('style');
    css.textContent = '#cc-consent{position:fixed;left:12px;right:12px;bottom:12px;z-index:2147483000;max-width:560px;margin:0 auto;background:#11232f;color:#edf2f2;border:1px solid #2c4757;border-radius:12px;padding:14px 16px;font:14px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;box-shadow:0 8px 30px rgba(0,0,0,.35)}'
      + '#cc-consent p{margin:0 0 10px}#cc-consent a{color:#efb875}#cc-consent .cc-b{display:flex;gap:8px;flex-wrap:wrap}'
      + '#cc-consent button{font:inherit;font-weight:600;border-radius:8px;padding:8px 16px;cursor:pointer;border:1px solid #efb875}'
      + '#cc-consent .cc-y{background:#efb875;color:#11232f}#cc-consent .cc-n{background:transparent;color:#efb875}';
    var box = document.createElement('div');
    box.id = 'cc-consent'; box.setAttribute('role', 'dialog'); box.setAttribute('aria-label', 'Cookie choice');
    box.innerHTML = '<p>May we use Google Analytics cookies to count visits and see which pages are useful? No ads, nothing sold. <a href="/privacy/#analytics">Privacy</a></p>'
      + '<div class="cc-b"><button type="button" class="cc-y">Accept</button><button type="button" class="cc-n">No thanks</button></div>';
    box.querySelector('.cc-y').onclick = function () { remember('yes'); gtag('consent', 'update', { analytics_storage: 'granted' }); box.remove(); };
    box.querySelector('.cc-n').onclick = function () { remember('no'); gtag('consent', 'update', off); box.remove(); };
    document.head.appendChild(css); document.body.appendChild(box);
  }
  function ready(f) { document.body ? f() : addEventListener('DOMContentLoaded', f); }
  if (european && !choice && !/^\/embed\//.test(location.pathname)) ready(banner);
  // "Cookie settings" buttons (Privacy page) reopen the choice anywhere.
  addEventListener('click', function (e) {
    var t = e.target && e.target.closest && e.target.closest('[data-cookie-settings]');
    if (t) { e.preventDefault(); ready(banner); }
  });
})();
