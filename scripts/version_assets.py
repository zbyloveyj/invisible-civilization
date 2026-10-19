#!/usr/bin/env python3
"""Version local published assets without changing reading URLs or saved data."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

ASSETS = {'.css', '.js', '.svg', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.ico', '.pdf'}
ATTRS = {'a': 'href', 'link': 'href', 'script': 'src', 'img': 'src', 'source': 'src'}
ATTR_RE = re.compile(r'''(?<![\w:-])(?P<key>href|src)\s*=\s*(?P<q>["'])(?P<value>.*?)(?P=q)''', re.I | re.S)


class AssetVersioner(HTMLParser):
    def __init__(self, source: str, page: Path, root: Path, prefix: str,
                 hashes: dict[Path, str]) -> None:
        super().__init__(convert_charrefs=False)
        self.source, self.page, self.root = source, page, root
        self.prefix, self.hashes = prefix, hashes
        self.edits: list[tuple[int, int, str]] = []
        self.offsets = [0]
        self.offsets.extend(m.end() for m in re.finditer('\n', source))

    def version(self, value: str) -> str:
        url = urlsplit(html.unescape(value))
        if url.scheme or url.netloc or not url.path:
            return value
        path = unquote(url.path)
        if Path(path).suffix.lower() not in ASSETS:
            return value
        if path.startswith('/'):
            if not path.startswith(self.prefix):
                return value
            target = (self.root / path[len(self.prefix):]).resolve()
        else:
            target = (self.page.parent / path).resolve()
        if not target.is_relative_to(self.root):
            return value
        if not target.is_file():
            raise ValueError(f'Missing local asset: {self.page.relative_to(self.root)} -> {path}')
        if target not in self.hashes:
            self.hashes[target] = hashlib.sha256(target.read_bytes()).hexdigest()[:12]
        query = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True) if k != 'v']
        query.append(('v', self.hashes[target]))
        return html.escape(urlunsplit((url.scheme, url.netloc, url.path,
                                      urlencode(query), url.fragment)), quote=True)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        wanted = ATTRS.get(tag)
        if wanted is None:
            return
        raw = self.get_starttag_text()
        line, col = self.getpos()
        start = self.offsets[line - 1] + col
        for match in ATTR_RE.finditer(raw):
            if match['key'].lower() != wanted:
                continue
            old = match['value']
            new = self.version(old)
            if new != old:
                self.edits.append((start + match.start('value'),
                                   start + match.end('value'), new))

    def render(self) -> str:
        self.feed(self.source)
        self.close()
        result = self.source
        for start, end, value in reversed(self.edits):
            result = result[:start] + value + result[end:]
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=Path('_site'))
    parser.add_argument('--prefix', default='/invisible-civilization/')
    args = parser.parse_args()
    root = args.site.resolve()
    if not (root / 'index.html').is_file():
        parser.error(f'No rendered homepage in {root}')
    hashes: dict[Path, str] = {}
    pages = list(root.rglob('*.html'))
    total = 0
    for page in pages:
        source = page.read_text(encoding='utf-8')
        editor = AssetVersioner(source, page, root, args.prefix, hashes)
        updated = editor.render()
        if updated != source:
            page.write_text(updated, encoding='utf-8')
        total += len(editor.edits)
    manifest = {
        'revision': os.environ.get('GITHUB_SHA', 'local'),
        'published_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'html_pages': len(pages),
        'assets': {p.relative_to(root).as_posix(): v for p, v in sorted(hashes.items())},
    }
    (root / 'site-version.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'PASS: {len(pages)} HTML pages; {len(hashes)} versioned assets; {total} updated links.')


if __name__ == '__main__':
    main()
