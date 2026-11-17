"""Build and publish the static Pages HTML to the gh-pages branch."""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).parent
sys.path.insert(0, str(REPORT))
from goatcounter import ensure_goatcounter

BASE = 'https://github.com/rudrakshsyal/dynamic_pricing_engine/blob/main/'
PAGES_HTML = ('index.html', 'supply_dashboard.html', 'demand_side_dashboard.html')


def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()


def github_links(html: str) -> str:
    """Point repository-relative report links at the public GitHub blobs."""
    html = html.replace('href="../../', 'href="' + BASE)
    html = html.replace(
        'href="LINKEDIN_DRAFT.md"',
        'href="' + BASE + 'reports/pricing-research/LINKEDIN_DRAFT.md"',
    )
    return html


def pages_documents() -> dict[str, str]:
    """HTML files GitHub Pages serves, including the count script on each."""
    documents = {
        'index.html': github_links((REPORT / 'index.html').read_text()),
        'supply_dashboard.html': (ROOT / 'supply_dashboard.html').read_text(),
        'demand_side_dashboard.html': (ROOT / 'demand_side_dashboard.html').read_text(),
    }
    return {name: ensure_goatcounter(html) for name, html in documents.items()}


def main():
    subprocess.run([sys.executable, str(REPORT / 'build.py')], check=True)
    remote = git('remote', 'get-url', 'origin')
    documents = pages_documents()
    with tempfile.TemporaryDirectory(prefix='dpe-pages-') as tmp:
        dest = Path(tmp)
        git('init', '-b', 'gh-pages', cwd=dest)
        git('remote', 'add', 'origin', remote, cwd=dest)
        if git('ls-remote', '--heads', 'origin', 'gh-pages', cwd=dest):
            git('fetch', 'origin', 'gh-pages', cwd=dest)
            git('checkout', '-B', 'gh-pages', 'FETCH_HEAD', cwd=dest)
        for name, html in documents.items():
            (dest / name).write_text(html)
        (dest / '.nojekyll').write_text('')
        git('config', 'user.name', git('config', 'user.name'), cwd=dest)
        git('config', 'user.email', git('config', 'user.email'), cwd=dest)
        git('add', *PAGES_HTML, '.nojekyll', cwd=dest)
        if git('status', '--porcelain', cwd=dest):
            git('commit', '-m', 'Publish pricing research dashboard', cwd=dest)
            git('push', 'origin', 'gh-pages', cwd=dest)
        else:
            print('Published files are already current.')


if __name__ == '__main__':
    main()
