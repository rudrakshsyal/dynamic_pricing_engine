import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from shutil import which

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "pricing-research"
sys.path.insert(0, str(REPORT))

from goatcounter import MARKER, SNIPPET, ensure_goatcounter
from publish import github_links, pages_documents

COUNT_SRC = 'src="//gc.zgo.at/count.js"'
ENDPOINT = "https://rudrakshsyal.goatcounter.com/count"


class PagesAnalyticsTests(unittest.TestCase):
    def test_snippet_is_inserted_once(self):
        page = "<html><body><p>Report</p></body></html>"
        once = ensure_goatcounter(page)
        twice = ensure_goatcounter(once)
        self.assertEqual(once, twice)
        self.assertEqual(once.count(MARKER), 1)
        self.assertIn(COUNT_SRC, once)
        self.assertLess(once.index(SNIPPET.strip()), once.index("</body>"))

    def test_each_pages_document_has_the_count_script(self):
        documents = pages_documents()
        self.assertEqual(set(documents), {"index.html", "supply_dashboard.html", "demand_side_dashboard.html"})
        for name, html in documents.items():
            with self.subTest(name=name):
                self.assertEqual(html.count(MARKER), 1, name)
                self.assertIn(COUNT_SRC, html)
                self.assertIn(ENDPOINT, html)
                self.assertIn("/dynamic_pricing_engine", html)
                self.assertIn("window.goatcounter.path", html)
                self.assertNotIn("no_referrer", html)
                self.assertNotIn("goatcounter.referrer", html)

    def test_report_numbers_and_dashboard_copy_stay(self):
        documents = pages_documents()
        report = documents["index.html"]
        self.assertIn("30.7% higher supply RMSE", report)
        self.assertIn("1.1% higher supply RMSE", report)
        self.assertIn("−5.2% to +2.5%", report)
        self.assertIn("var changed=tabs[i].getAttribute('aria-selected')!=='true'", report)
        self.assertIn("Supply overview", documents["supply_dashboard.html"])
        self.assertIn("12400", documents["supply_dashboard.html"])
        self.assertIn("Demand overview", documents["demand_side_dashboard.html"])
        self.assertIn("$12.7k", documents["demand_side_dashboard.html"])

    def test_published_report_links_point_at_github(self):
        published = pages_documents()["index.html"]
        self.assertNotIn('href="../../', published)
        self.assertNotIn('href="LINKEDIN_DRAFT.md"', published)
        self.assertIn(
            "https://github.com/rudrakshsyal/dynamic_pricing_engine/blob/main/docs/SYNTHETIC_ROBUSTNESS.md",
            published,
        )
        self.assertIn(
            "https://github.com/rudrakshsyal/dynamic_pricing_engine/blob/main/reports/pricing-research/LINKEDIN_DRAFT.md",
            published,
        )
        source = (REPORT / "index.html").read_text()
        self.assertIn('href="../../docs/SYNTHETIC_ROBUSTNESS.md"', source)
        self.assertEqual(github_links(source).count(MARKER), 1)

    def test_path_prefix_and_events(self):
        node = which("node")
        if node is None:
            self.skipTest("node is not installed")
        snippet_path = _write_snippet()
        script = r"""
const fs = require('fs');
const snippet = fs.readFileSync(process.argv[1], 'utf8');
const source = snippet.split('<script>')[1].split('</script>')[0];
global.window = global;
global.location = {href: 'https://rudrakshsyal.github.io/dynamic_pricing_engine/'};
global.document = {addEventListener() {}};
eval(source);
const path = window.goatcounter.path;
const base = 'https://rudrakshsyal.github.io/dynamic_pricing_engine/';
const paths = {
  '/': '/dynamic_pricing_engine/',
  '/index.html': '/dynamic_pricing_engine/',
  '/dynamic_pricing_engine': '/dynamic_pricing_engine/',
  '/dynamic_pricing_engine/': '/dynamic_pricing_engine/',
  '/dynamic_pricing_engine/index.html': '/dynamic_pricing_engine/',
  '/dynamic_pricing_engine/index.html?utm=linkedin': '/dynamic_pricing_engine/?utm=linkedin',
  '/dynamic_pricing_engine/supply_dashboard.html': '/dynamic_pricing_engine/supply_dashboard.html',
  '/dynamic_pricing_engine/demand_side_dashboard.html': '/dynamic_pricing_engine/demand_side_dashboard.html',
  '/foo': '/dynamic_pricing_engine/foo',
  'outbound-github': 'outbound-github'
};
for (const [input, expected] of Object.entries(paths)) {
  const actual = path(input);
  if (actual !== expected) {
    console.error(JSON.stringify({kind: 'path', input, expected, actual}));
    process.exit(1);
  }
}
const events = [
  ['https://github.com/rudrakshsyal/dynamic_pricing_engine/blob/main/docs/SYNTHETIC_ROBUSTNESS.md', '', 'outbound-github'],
  ['https://github.com/rudrakshsyal/dynamic_pricing_engine/blob/main/experiments/automl_grid_v1/comparison_results.json', '', 'outbound-github'],
  ['https://github.com/rudrakshsyal/ai_portfolio', '', 'outbound-portfolio'],
  ['https://github.com/rudrakshsyal/ai_portfolio/blob/main/README.md', '', 'outbound-portfolio'],
  ['https://rudrakshsyal.github.io/ai_portfolio/', '', 'outbound-portfolio'],
  ['https://rudraksh-syal-portfolio.glasnost.chatgpt.site/work', '', 'outbound-portfolio'],
  ['https://rudrakshsyal.github.io/dynamic_pricing_engine/supply_dashboard.html', '', null],
  ['https://www.linkedin.com/in/rudraksh-syal', '', null],
  ['#methods', '', null],
  ['mailto:rudrakshsyal@gmail.com', '', null],
  ['https://example.com/files/report.pdf', '', 'download-report.pdf'],
  ['https://example.com/files/report.pdf', 'saved.pdf', 'download-saved.pdf'],
  ['https://raw.githubusercontent.com/rudrakshsyal/dynamic_pricing_engine/main/README.md', '', 'download-README.md'],
  ['https://github.com/rudrakshsyal/dynamic_pricing_engine/releases/download/v1/results.csv', '', 'download-results.csv']
];
for (const [href, download, expected] of events) {
  const actual = window.gcEventName(href, {base, download});
  if (actual !== expected) {
    console.error(JSON.stringify({kind: 'event', href, download, expected, actual}));
    process.exit(1);
  }
}
const calls = [];
window.goatcounter.count = (payload) => calls.push(payload);
window.gcTrack('tab-research');
window.gcTrack('outbound-github');
if (calls.length !== 2 || calls[0].path !== 'tab-research' || calls[0].event !== true || calls[1].referrer !== undefined) {
  console.error(JSON.stringify({kind: 'track', calls}));
  process.exit(1);
}
const tab = {id: 'agent-tab', getAttribute() { return ''; }};
if (window.gcTabName(tab) !== 'tab-agent') process.exit(1);
const button = {id: '', getAttribute(name) { return name === 'onclick' ? "dSw('el',this)" : ''; }};
if (window.gcTabName(button) !== 'tab-el') process.exit(1);
console.log('ok');
"""
        completed = subprocess.run(
            [node, "-e", script, snippet_path],
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertIn("ok", completed.stdout)

    def test_click_tracking_does_not_cancel_navigation(self):
        node = which("node")
        if node is None:
            self.skipTest("node is not installed")
        snippet_path = _write_snippet()
        probe = r"""
const fs = require('fs');
const snippet = fs.readFileSync(process.argv[1], 'utf8');
const source = snippet.split('<script>')[1].split('</script>')[0];
global.window = global;
global.location = {href: 'https://rudrakshsyal.github.io/dynamic_pricing_engine/'};
let listener;
global.document = {addEventListener(type, fn) { listener = fn; }};
eval(source);
window.goatcounter.count = () => {};
const prevented = [];
const anchor = {
  tag: 'a',
  href: 'https://github.com/rudrakshsyal/dynamic_pricing_engine',
  hasAttribute(name) { return false; },
  getAttribute(name) { return name === 'href' ? this.href : null; },
  closest(sel) { return sel === 'a' ? this : null; }
};
const event = {
  target: anchor,
  preventDefault() { prevented.push('anchor'); },
  stopPropagation() { prevented.push('stop'); }
};
listener(event);
const tab = {
  tag: 'button',
  id: 'research-tab',
  className: '',
  getAttribute(name) { return name === 'aria-selected' ? 'false' : (name === 'onclick' ? null : ''); },
  classList: {contains() { return false; }},
  closest(sel) { return sel.includes('tab') ? this : null; }
};
listener({target: tab, preventDefault() { prevented.push('tab'); }, stopPropagation() { prevented.push('stop'); }});
if (prevented.length) {
  console.error(prevented.join(','));
  process.exit(1);
}
console.log('ok');
"""
        completed = subprocess.run(
            [node, "-e", probe, snippet_path],
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)


def _write_snippet():
    handle = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False)
    handle.write(SNIPPET)
    handle.close()
    return handle.name


if __name__ == "__main__":
    unittest.main()
