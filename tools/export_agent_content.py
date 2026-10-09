"""Export only public posts, without credentials; also runs in GitHub Actions."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import sys
from pathlib import Path
from urllib.parse import urlparse
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from blog_generator.core.agent_content import BLOG_URL, RAW_URL, article_markdown


def public_posts():
    posts, start = [], 1
    while True:
        response = requests.get(BLOG_URL + '/feeds/posts/default', params={'alt': 'json', 'max-results': 100, 'start-index': start, 'orderby': 'published'}, timeout=60)
        response.raise_for_status()
        entries = response.json()['feed'].get('entry', [])
        for e in entries:
            url = next(link['href'] for link in e['link'] if link['rel'] == 'alternate')
            posts.append({'id': e['id']['$t'].split('post-')[-1], 'url': url, 'title': e['title']['$t'], 'published': e['published']['$t'], 'updated': e['updated']['$t'], 'labels': [c['term'] for c in e.get('category', [])], 'content': e['content']['$t'], 'author': {'displayName': e.get('author', [{}])[0].get('name', {}).get('$t', 'DevOpsDreams')}})
        if len(entries) < 100:
            break
        start += len(entries)
    if not posts:
        raise RuntimeError('Empty public feed: retain previous exports')
    return posts


def export(posts, out):
    out.mkdir(parents=True, exist_ok=True)
    (out/'articles').mkdir(exist_ok=True)
    records = []
    for post in posts:
        text = article_markdown(post)
        path = 'articles/' + post['id'] + '.md'
        (out/path).write_text(text, encoding='utf-8')
        records.append({k: post.get(k) for k in ['id', 'title', 'url', 'published', 'updated', 'labels', 'author']} | {'markdown_url': RAW_URL+'/'+path, 'markdown_path': path, 'sha256': hashlib.sha256(text.encode()).hexdigest()})
    expected = {p['id']+'.md' for p in posts}
    # Only prune generated .md files within the dedicated article output directory.
    for path in (out/'articles').glob('*.md'):
        if path.name not in expected:
            path.unlink()
    (out/'catalog.json').write_text(json.dumps({'source':BLOG_URL,'articles':records},ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    lines = ['# DevOpsDreams', '', '> Published guides to AWS, Kubernetes, Terraform, GitOps and platform reliability.', '', 'Use each article\'s Source URL when citing it. Dates and software assumptions belong to the individual article. Only published content is exported.', '', '## Guides', '']
    lines += [f"- [{p['title']}]({p['markdown_url']}): Topics: {', '.join(p['labels'] or [])}. Original: {p['url']}" for p in records]
    (out/'llms.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (out/'README.md').write_text('# DevOpsDreams published guides\n\nRead the [blog]('+BLOG_URL+') or use [llms.txt](llms.txt), [catalog.json](catalog.json), and [Markdown articles](articles).\n\nThis repository contains published content only. Cite the Source URL in each article. An automated public-feed refresh runs hourly and can be dispatched manually. Exports include original publication/update dates and author attribution. No Blogger credentials or drafts are needed. The llms.txt file is an optional agent navigation aid, not a search-ranking guarantee.\n',encoding='utf-8')
    return records


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default='data/agent-content-exports')
    args=parser.parse_args()
    records=export(public_posts(),Path(args.out))
    print(json.dumps({'published_articles':len(records),'output':args.out}))
