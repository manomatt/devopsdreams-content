"""Published article transformations shared by Blogger and the public export job."""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from markdownify import markdownify

BLOG_URL = 'https://devopsdreams.blogspot.com'
RAW_URL = 'https://raw.githubusercontent.com/manomatt/devopsdreams-content/main'


def anchor_html(content: str) -> str:
    # Patch opening tags only: do not reserialize legacy SVG, code, or image HTML.
    existing = set(re.findall(r'\bid=["\']([^"\']+)', content))
    h2_number = 0
    counts = {}
    def heading(match):
        nonlocal h2_number
        level, attrs, text = match.groups()
        if level == '2':
            h2_number += 1
        if re.search(r'\bid\s*=', attrs):
            return match.group()
        # Preserve the theme's historical H2 bookmark destinations.
        plain = BeautifulSoup(text, 'html.parser').get_text(' ', strip=True)
        base = f'dd-section-{h2_number}' if level == '2' else 'dd-' + re.sub(r'[^a-z0-9]+', '-', plain.lower()).strip('-')[:90]
        candidate = base
        while candidate in existing:
            counts[base] = counts.get(base, 1) + 1
            candidate = f'{base}-{counts[base]}'
        existing.add(candidate)
        return f'<h{level}{attrs} id="{candidate}">{text}</h{level}>'
    return re.sub(r'<h([23])\b([^>]*)>([\s\S]*?)</h\1>', heading, content, flags=re.I)


def article_markdown(post: dict) -> str:
    soup = BeautifulSoup(post['content'], 'html.parser')
    for node in soup.select('script,style,.dd-toc,.dd-agent-actions,.dd-agent-note'):
        node.decompose()
    for node in soup.select('a[href],img[src]'):
        attr = 'href' if node.name == 'a' else 'src'
        node[attr] = urljoin(post['url'], node[attr])
    for svg in soup.find_all('svg'):
        labels = svg.get_text(' ', strip=True)
        svg.replace_with(soup.new_string('\nDiagram labels: ' + labels + '\n'))
    for image in soup.find_all('img'):
        if not image.get('alt', '').strip():
            image['alt'] = 'Article image; see surrounding explanation'
    def language(el):
        code = el.find('code')
        classes = (code or el).get('class', [])
        return next((c.removeprefix('language-') for c in classes if c.startswith('language-')), '')
    body = markdownify(str(soup), heading_style='ATX', bullets='-', code_language_callback=language).strip()
    title = post['title'].strip()
    if body.startswith('# ' + title):
        body = body[len('# ' + title):].lstrip()
    tags = ', '.join(post.get('labels', []))
    return f"# {title}\n\nSource: {post['url']}\nPublished: {post.get('published', '')}\nUpdated: {post.get('updated', '')}\nAuthor: {post.get('author', {}).get('displayName', 'DevOpsDreams')}\nTopics: {tags}\n\n{body}\n"
