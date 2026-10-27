"""Check relative Markdown links and image references without network requests."""
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
errors = []
count = 0
for document in [root / 'README.md', root / 'CONTRIBUTING.md', root / 'CHANGELOG.md', root / 'SECURITY.md', *root.glob('docs/**/*.md'), *root.glob('benchmarks/**/README.md')]:
    for match in re.finditer(r'\]\(([^)]+)\)', document.read_text()):
        target = match[1].split('#')[0]
        if not target or '://' in target or target.startswith('mailto:'):
            continue
        count += 1
        if not (document.parent / target).exists():
            errors.append(f'{document.relative_to(root)}: {target}')
if errors:
    raise SystemExit('\n'.join(errors))
print(f'{count} relative documentation links verified')
