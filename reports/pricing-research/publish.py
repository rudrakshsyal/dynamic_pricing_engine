"""Build and publish only the static dashboard to the gh-pages branch."""
import subprocess
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).parent
BASE = 'https://github.com/rudrakshsyal/dynamic_pricing_engine/blob/main/'

def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()

subprocess.run([sys.executable, str(REPORT/'build.py')], check=True)
remote = git('remote', 'get-url', 'origin')
with tempfile.TemporaryDirectory(prefix='dpe-pages-') as tmp:
    dest = Path(tmp)
    git('init', '-b', 'gh-pages', cwd=dest)
    git('remote', 'add', 'origin', remote, cwd=dest)
    if git('ls-remote', '--heads', 'origin', 'gh-pages', cwd=dest):
        git('fetch', 'origin', 'gh-pages', cwd=dest)
        git('checkout', '-B', 'gh-pages', 'FETCH_HEAD', cwd=dest)
    html = (REPORT/'index.html').read_text()
    html = html.replace('href="../../', 'href="'+BASE)
    html = html.replace('href="LINKEDIN_DRAFT.md"', 'href="'+BASE+'reports/pricing-research/LINKEDIN_DRAFT.md"')
    (dest/'index.html').write_text(html)
    (dest/'.nojekyll').write_text('')
    git('config', 'user.name', git('config', 'user.name'), cwd=dest)
    git('config', 'user.email', git('config', 'user.email'), cwd=dest)
    git('add', 'index.html', '.nojekyll', cwd=dest)
    if git('status', '--porcelain', cwd=dest):
        git('commit', '-m', 'Publish pricing research dashboard', cwd=dest)
        git('push', 'origin', 'gh-pages', cwd=dest)
    else:
        print('Published files are already current.')
