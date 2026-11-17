"""Cookie-less GoatCounter snippet for the GitHub Pages HTML files.

The count script is the standard GoatCounter tag for the existing site code
``rudrakshsyal``. Page paths are prefixed with ``/dynamic_pricing_engine`` so
they stay separate from the portfolio site's ``/`` path. Referrer is not
overridden, so GoatCounter still records ``document.referrer`` (LinkedIn
traffic included). Localhost and ``file:`` views are ignored by GoatCounter's
own defaults.
"""

SNIPPET = """<script>
window.goatcounter = window.goatcounter || {};
// Prefix page views so this project does not share the portfolio's "/" path.
// Leave event names (no leading slash) unchanged. Do not set referrer.
window.goatcounter.path = function (p) {
  if (!p || p.charAt(0) !== '/') return p;
  var query = '';
  var q = p.indexOf('?');
  if (q >= 0) { query = p.slice(q); p = p.slice(0, q); }
  var prefix = '/dynamic_pricing_engine';
  if (p !== prefix && p.indexOf(prefix + '/') !== 0) p = prefix + p;
  if (p === prefix) p = prefix + '/';
  p = p.replace(/\\/index\\.html$/, '/');
  return p + query;
};
window.gcTrack = function (name) {
  try {
    if (!name || !window.goatcounter || typeof window.goatcounter.count !== 'function') return;
    window.goatcounter.count({path: name, event: true});
  } catch (err) {}
};
window.gcEventName = function (href, opts) {
  opts = opts || {};
  if (!href) return null;
  var value = String(href).trim();
  if (!value || value.charAt(0) === '#' || /^javascript:/i.test(value)) return null;
  var base = opts.base || location.href;
  var url;
  try { url = new URL(value, base); }
  catch (err) { return null; }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
  var host = url.hostname.replace(/^www\\./, '').toLowerCase();
  var path = url.pathname || '/';
  var leaf = path.split('/').pop() || '';
  var dot = leaf.lastIndexOf('.');
  var ext = dot > 0 ? leaf.slice(dot + 1).toLowerCase() : '';
  var downloadExt = {pdf:1, csv:1, tsv:1, zip:1, gz:1, tgz:1, xlsx:1, xls:1, parquet:1, '7z':1};
  var githubBlob = host === 'github.com' && path.indexOf('/blob/') !== -1;
  var rawFile = host === 'raw.githubusercontent.com' || (host === 'github.com' && (path.indexOf('/raw/') !== -1 || path.indexOf('/releases/download/') !== -1));
  if (opts.download || rawFile || (!githubBlob && downloadExt[ext])) {
    var preferred = (typeof opts.download === 'string' && opts.download) ? opts.download : leaf;
    var name = String(preferred || 'file').split(/[?#]/)[0];
    name = name.replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80) || 'file';
    return 'download-' + name;
  }
  var portfolio = (host === 'github.com' && /\\/rudrakshsyal\\/ai_portfolio(?:\\/|$)/.test(path))
    || (host === 'rudrakshsyal.github.io' && (path === '/ai_portfolio' || path.indexOf('/ai_portfolio/') === 0))
    || host.indexOf('rudraksh-syal-portfolio') === 0;
  if (portfolio) return 'outbound-portfolio';
  if (host === 'rudrakshsyal.github.io' && (path === '/dynamic_pricing_engine' || path.indexOf('/dynamic_pricing_engine/') === 0)) return null;
  var github = host === 'github.com' || host.endsWith('.github.com') || host === 'github.io' || host.endsWith('.github.io') || host === 'githubusercontent.com' || host.endsWith('.githubusercontent.com');
  if (github) return 'outbound-github';
  return null;
};
window.gcTabName = function (tab) {
  if (!tab) return null;
  var id = tab.id || '';
  if (id) return 'tab-' + id.replace(/-tab$/, '');
  var onclick = tab.getAttribute('onclick') || '';
  var match = onclick.match(/(?:sSw|dSw)\\('([^']+)'/);
  return match ? 'tab-' + match[1] : null;
};
document.addEventListener('click', function (event) {
  try {
    var node = event.target;
    if (!node || !node.closest) return;
    var tab = node.closest('[role="tab"], .sbtn, .tbtn');
    if (tab && tab.getAttribute('aria-selected') !== 'true' && !tab.classList.contains('act')) {
      window.gcTrack(window.gcTabName(tab));
    }
    var anchor = node.closest('a');
    if (!anchor) return;
    var download = anchor.hasAttribute('download') ? (anchor.getAttribute('download') || true) : '';
    window.gcTrack(window.gcEventName(anchor.getAttribute('href'), {download: download}));
  } catch (err) {}
}, true);
</script>
<script data-goatcounter="https://rudrakshsyal.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
"""

MARKER = 'data-goatcounter="https://rudrakshsyal.goatcounter.com/count"'


def ensure_goatcounter(html: str) -> str:
    """Insert the count script once, immediately before ``</body>`` when present."""
    if MARKER in html:
        return html
    if "</body>" in html:
        return html.replace("</body>", SNIPPET + "</body>", 1)
    return html + "\n" + SNIPPET
