#!/usr/bin/env python3
"""Refresh the live-data blocks in index.html from public sources.

Every number and list this script writes comes from a live, public source:

  blog.msdevbuild.com/rss.xml                   latest articles, article + shorts counts
  blog.msdevbuild.com/blog/<slug>/              each article's share image (og:image)
  github.com/jssuthahar/blog  src/config.ts     verified reach figures (IMPACT)
  github.com/jssuthahar/blog  src/content/events  events
  www.msdevbuild.com Blogger feed               archive article count
  api.github.com                                followers, repos, stars, forks, commits
  YouTube channel feed                          latest videos

Blocks live between <!-- data:NAME --> and <!-- /data:NAME --> markers, and
single values in <span data-k="NAME">…</span>. If a source fails, that block
keeps its current content — the page is never blanked by a network hiccup.

Usage:  python3 tools/build.py            (stdlib only, Python 3.9+)
        GITHUB_TOKEN=… python3 tools/build.py   (higher GitHub API limit in CI)
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
SITE = 'https://suthahar.msdevbuild.com/'
BLOG = 'https://blog.msdevbuild.com'
GH_USER = 'jssuthahar'
YT_CHANNEL = 'UCPwZsK00EZDfIrj5DCYyuPA'
TODAY = dt.date.today().isoformat()

# Repos left out of "featured": the Azure platform has its own card; Malaysia is a vlog, not code.
REPO_SKIP = {'Azure', 'Malaysia'}
LANG_COLOUR = {'C#': '#178600', 'HTML': '#e34c26', 'JavaScript': '#f1e05a', 'C++': '#f34b7d', 'Java': '#b07219',
               'TypeScript': '#3178c6', 'Dart': '#00b4ab', 'Astro': '#ff5a03', 'Python': '#3572a5', 'CSS': '#563d7c'}
CATEGORY = {'azure': 'Azure', 'ai': 'AI', 'web': 'Web · .NET', 'copilot': 'GitHub Copilot', 'career': 'Career'}

warnings: list[str] = []


# ---------------------------------------------------------------- fetching
def get(url: str, *, json_=False, headers: dict | None = None, raw=False):
    h = {'User-Agent': 'suthahar-profile-build', 'Accept': 'application/json' if json_ else '*/*'}
    if 'api.github.com' in url and os.environ.get('GITHUB_TOKEN'):
        h['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=25) as r:
        if raw:
            return r
        body = r.read().decode('utf-8', 'replace')
    return json.loads(body) if json_ else body


def esc(s: str) -> str:
    return html.escape(s or '', quote=True)


def nice_date(iso: str) -> str:
    return dt.date.fromisoformat(iso[:10]).strftime('%d %b %Y').lstrip('0')


# ---------------------------------------------------------------- sources
def blog_feed():
    root = ET.fromstring(get(f'{BLOG}/rss.xml'))
    posts, shorts = [], 0
    for it in root.iter('item'):
        link = (it.findtext('link') or '').rstrip('/')
        if '/shorts/' in link:
            shorts += 1
            continue
        if '/blog/' not in link:
            continue
        pub = dt.datetime.strptime(it.findtext('pubDate')[:16], '%a, %d %b %Y').date().isoformat()
        cats = [c.text for c in it.findall('category') if c.text]
        posts.append(dict(title=it.findtext('title'), link=link + '/', desc=it.findtext('description') or '',
                          date=pub, cat=cats[0] if cats else 'Article'))
    posts.sort(key=lambda p: p['date'], reverse=True)
    return posts, shorts


def og_image(url: str) -> str:
    try:
        m = re.search(r'<meta property="og:image" content="([^"]+)"', get(url))
        return m.group(1) if m else ''
    except Exception:
        return ''


def impact_figures():
    src = get(f'https://raw.githubusercontent.com/{GH_USER}/blog/main/src/config.ts')
    block = re.search(r'export const IMPACT = \[(.*?)\]', src, re.S).group(1)
    return {label: value for value, label in re.findall(r"value:\s*'([^']+)',\s*label:\s*'([^']+)'", block)}


def events():
    listing = get(f'https://api.github.com/repos/{GH_USER}/blog/contents/src/content/events', json_=True)
    out = []
    for f in listing:
        if not f['name'].endswith('.md') or f['name'] == 'README.md':
            continue
        fm = re.match(r'---\n(.*?)\n---', get(f['download_url']), re.S).group(1)
        g = lambda k: (re.search(rf'^{k}:\s*(.*)$', fm, re.M) or [None, ''])[1].strip().strip('\'"')
        out.append(dict(slug=f['name'][:-3], title=g('title'), desc=g('description'), date=g('startDate')[:10],
                        fmt=g('format'), loc=g('location') or 'Online'))
    return sorted(out, key=lambda e: e['date'], reverse=True)


def archive_count() -> int:
    d = get('https://www.msdevbuild.com/feeds/posts/summary?alt=json&max-results=0', json_=True)
    return int(d['feed']['openSearch$totalResults']['$t'])


def github():
    user = get(f'https://api.github.com/users/{GH_USER}', json_=True)
    repos = get(f'https://api.github.com/users/{GH_USER}/repos?per_page=100&type=owner', json_=True)
    repos = [r for r in repos if not r['fork']]
    art = get(f'https://api.github.com/repos/{GH_USER}/Article', json_=True)
    link = get(f'https://api.github.com/repos/{GH_USER}/Article/commits?per_page=1', raw=True).headers.get('Link', '')
    commits = int(re.search(r'page=(\d+)>; rel="last"', link).group(1)) if 'rel="last"' in link else 0
    return dict(followers=user['followers'], public_repos=user['public_repos'],
                stars=sum(r['stargazers_count'] for r in repos), forks=sum(r['forks_count'] for r in repos),
                repos=repos, art_stars=art['stargazers_count'], art_forks=art['forks_count'], art_commits=commits)


def youtube(limit=6):
    ns = {'a': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}
    root = ET.fromstring(get(f'https://www.youtube.com/feeds/videos.xml?channel_id={YT_CHANNEL}'))
    vids, seen = [], set()
    for e in root.findall('a:entry', ns):
        title = e.findtext('a:title', namespaces=ns) or ''
        if '#shorts' in title.lower() or 'apple watch' in title.lower():   # keep it to lessons
            continue
        clean = re.sub(r'\s*#\S+', '', title)
        clean = re.sub(r'\s*@\S+', '', clean)
        clean = re.sub(r'[^\w\s.,:|#+&()\'’-]', '', clean).strip(' |-')
        clean = re.sub(r'\s{2,}', ' ', clean)
        key = ' '.join(clean.lower().split()[:3])            # drop near-duplicate re-uploads
        if key in seen:
            continue
        seen.add(key)
        vids.append(dict(id=e.findtext('yt:videoId', namespaces=ns), title=clean,
                         date=(e.findtext('a:published', namespaces=ns) or '')[:10],
                         tamil='tamil' in title.lower() or 'தமிழ்' in title))
        if len(vids) == limit:
            break
    return vids


# ---------------------------------------------------------------- renderers
def r_stats(imp, total_articles, shorts):
    items = [(imp['Years in enterprise architecture'], 'Years in architecture'), (imp['Total content views'], 'Content views'),
             (imp['Developers reached'], 'Developers reached'), (imp['Conference talks delivered'], 'Conference talks'),
             (str(total_articles), 'Published articles'), (str(shorts), 'Short videos')]
    cells = '\n'.join(f'    <div class="stat-item"><div class="stat-n">{n}</div><div class="stat-l">{l}</div></div>' for n, l in items)
    return f'''<div class="stats-bar" aria-label="At a glance">
  <div class="stats-inner">
{cells}
  </div>
  <p class="stat-src">Reach figures from <a href="{BLOG}/about/" target="_blank" rel="noopener">blog.msdevbuild.com/about</a>; counts from the live MSDEVBUILD feeds, updated <time datetime="{TODAY}">{nice_date(TODAY)}</time>.</p>
</div>'''


def r_impact(imp, archive, posts_n, gh):
    rows = [(imp['Years in enterprise architecture'], 'Years in enterprise architecture', 'Since 2007'),
            (imp['Total content views'], 'Total content views', 'Across MSDEVBUILD'),
            (imp['Developers reached'], 'Developers &amp; students reached', 'Mentoring since 2007'),
            (imp['Conference talks delivered'], 'Conference talks delivered', 'Community &amp; events'),
            ('15+', 'Enterprise mobile apps architected', 'Xamarin / .NET MAUI + Azure'),
            ('~20%', 'Cloud spend reduced', 'FinOps at Continental Tire'),
            (str(archive + posts_n), 'Published articles', f'{archive} msdevbuild.com + {posts_n} blog'),
            (str(gh['public_repos']), 'Public GitHub repositories', '@jssuthahar')]
    cells = '\n'.join(f'      <div class="impact-card"><div class="impact-n">{n}</div><div class="impact-l">{l}</div><div class="impact-s">{s}</div></div>'
                      for n, l, s in rows)
    return f'    <div class="impact-grid">\n{cells}\n    </div>'


def r_blog(posts, archive, shorts):
    cards = []
    for p in posts[:6]:
        og = og_image(p['link'])
        img = (f'<div class="bc-top"><img src="{esc(og)}" alt="" width="1200" height="630" loading="lazy" decoding="async"></div>'
               if og else '<div class="bc-top bc-top--empty" aria-hidden="true"></div>')
        cards.append(f'''      <a class="blog-card" href="{esc(p['link'])}" target="_blank" rel="noopener">
        {img}
        <div class="bc-body">
          <div class="bc-cat"><span>{esc(CATEGORY.get(p['cat'].lower(), p['cat']))}</span><time datetime="{p['date']}">{nice_date(p['date'])}</time></div>
          <h3 class="bc-t">{esc(p['title'])}</h3>
          <p class="bc-sn">{esc(p['desc'])}</p>
          <span class="bc-rd">Read article →</span>
        </div>
      </a>''')
    return f'''    <div class="platforms">
      <a class="platform" href="{BLOG}/" target="_blank" rel="noopener"><b>Blog</b><strong>blog.msdevbuild.com</strong><span>Architect-level articles on Azure, Microsoft Foundry, AI agents, GitHub Copilot, C#, Flutter and .NET MAUI — real code, real trade-offs.</span><em>{len(posts)} articles · {shorts} shorts →</em></a>
      <a class="platform" href="https://azure.msdevbuild.com/" target="_blank" rel="noopener"><b>Open source · Learning</b><strong>azure.msdevbuild.com</strong><span>Free Azure certification learning platform — AZ-900 tutorials, mock exams and interview prep. Open source on GitHub.</span><em>Start AZ-900 →</em></a>
      <a class="platform" href="https://www.msdevbuild.com/" target="_blank" rel="noopener"><b>Archive</b><strong>msdevbuild.com</strong><span>The original MSDEVBUILD blog — tutorials on Xamarin, .NET MAUI, Azure, C# and more, published since 2011.</span><em>{archive} articles →</em></a>
    </div>
    <div class="blog-grid">
{chr(10).join(cards)}
    </div>'''


def r_youtube(vids):
    cards = '\n'.join(f'''      <a class="video-card" href="https://www.youtube.com/watch?v={v['id']}" target="_blank" rel="noopener">
        <div class="vc-thumb"><img src="https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg" alt="" width="480" height="360" loading="lazy" decoding="async"><span class="vc-play" aria-hidden="true">▶</span></div>
        <div class="vc-body"><div class="vc-cat">{'Tamil' if v['tamil'] else 'English'}</div><h3 class="vc-t">{esc(v['title'])}</h3><div class="vc-dur"><time datetime="{v['date']}">{nice_date(v['date'])}</time></div></div>
      </a>''' for v in vids)
    return f'    <div class="video-grid">\n{cards}\n    </div>'


def r_opensource(gh):
    skip = REPO_SKIP | {'Article', GH_USER}          # Article has its own card; GH_USER is the profile README
    top = sorted((r for r in gh['repos'] if r['name'] not in skip),
                 key=lambda r: r['stargazers_count'] + r['forks_count'], reverse=True)[:6]

    def card(r):
        d = (r['description'] or 'Public repository').strip()
        if len(d) > 150:
            d = d[:147].rsplit(' ', 1)[0] + '…'
        lang = r.get('language')
        lg = f'<span><i class="dot" style="background:{LANG_COLOUR.get(lang, "#8b949e")}"></i>{esc(lang)}</span>' if lang else ''
        return f'''      <a class="repo-card" href="{r['html_url']}" target="_blank" rel="noopener">
        <div class="repo-n">{esc(r['name'])} <small>Public</small></div>
        <p class="repo-d">{esc(d)}</p>
        <div class="repo-m">{lg}<span>★ {r['stargazers_count']}</span><span>⑂ {r['forks_count']}</span></div>
      </a>'''
    return f'''    <div class="gh-hero band-panel">
      <div class="gh-id">
        <div class="gh-av"><img src="images/suthahar-jegatheesan-160.webp" alt="" width="76" height="76" loading="lazy"></div>
        <div><div class="gh-name">@{GH_USER}</div><div class="gh-sub">Cloud, AI, Mobile &amp; .NET — the code behind MSDEVBUILD</div>
          <div class="gh-actions"><a class="gh-btn" href="https://github.com/{GH_USER}" target="_blank" rel="noopener">⌥ Follow on GitHub</a><a class="gh-btn gh-btn--ghost" href="https://github.com/{GH_USER}?tab=repositories" target="_blank" rel="noopener">All repositories</a></div>
        </div>
      </div>
      <div class="gh-stats">
        <div class="gh-stat"><b>{gh['public_repos']}</b><span>Public repos</span></div>
        <div class="gh-stat"><b>{gh['followers']}</b><span>Followers</span></div>
        <div class="gh-stat"><b>{gh['stars']}</b><span>Stars</span></div>
        <div class="gh-stat"><b>{gh['forks']}</b><span>Forks</span></div>
      </div>
    </div>
    <div class="repo-grid">
      <a class="repo-card featured" href="https://azure.msdevbuild.com/" target="_blank" rel="noopener">
        <div class="repo-ico" aria-hidden="true">☁</div>
        <div><div class="repo-n">{GH_USER} / Azure <small>Open source</small></div><p class="repo-d">MSDEVBUILD Azure — a free, open-source learning platform for Microsoft Azure certifications: AZ-900 tutorials, question banks, mock exams and interview prep. Live at <b>azure.msdevbuild.com</b>; source at github.com/{GH_USER}/Azure.</p></div>
        <span class="gh-btn gh-btn--azure">Open site ↗</span>
      </a>
      <a class="repo-card featured" href="https://github.com/{GH_USER}/Article" target="_blank" rel="noopener">
        <div class="repo-ico" aria-hidden="true">📚</div>
        <div><div class="repo-n">{GH_USER} / Article <small>Public</small></div><p class="repo-d">The MSDEVBUILD article repository — tutorials across Azure, C#, .NET, Flutter, Python, SQL, WPF, careers and interview prep. <b>★ {gh['art_stars']}</b> · <b>⑂ {gh['art_forks']}</b> · <b>{gh['art_commits']} commits</b>.</p></div>
        <span class="gh-btn gh-btn--azure">Browse ↗</span>
      </a>
{chr(10).join(card(r) for r in top)}
    </div>
    <p class="data-note">Numbers from the GitHub API, updated <time datetime="{TODAY}">{nice_date(TODAY)}</time>.</p>'''


def r_events(evs):
    cards = '\n'.join(f'''      <a class="ev-card" href="{BLOG}/events/{e['slug']}/" target="_blank" rel="noopener">
        <div class="ev-date"><time datetime="{e['date']}">{nice_date(e['date'])}</time><span class="ev-fmt">{esc(e['fmt'])}</span></div>
        <h3 class="ev-t">{esc(e['title'])}</h3>
        <p class="ev-d">{esc(e['desc'])}</p>
        <span class="ev-l">{esc(e['loc'])} · Details →</span>
      </a>''' for e in evs)
    return f'    <div class="ev-grid">\n{cards}\n    </div>'


# ---------------------------------------------------------------- writing
def put_block(doc: str, name: str, content: str) -> str:
    pat = re.compile(rf'(<!-- data:{name} -->)(.*?)(<!-- /data:{name} -->)', re.S)
    if not pat.search(doc):
        warnings.append(f'marker data:{name} missing')
        return doc
    return pat.sub(lambda m: m.group(1) + '\n' + content + '\n' + m.group(3), doc, count=1)


def put_value(doc: str, key: str, value) -> str:
    return re.sub(rf'(<span data-k="{key}">)[^<]*(</span>)', rf'\g<1>{value}\2', doc)


def step(label, fn, *a):
    try:
        return fn(*a)
    except Exception as e:  # keep the old block; report and carry on
        warnings.append(f'{label}: {e.__class__.__name__}: {e}')
        return None


def main() -> int:
    doc = open(INDEX, encoding='utf-8').read()
    before = doc

    feed = step('blog feed', blog_feed)
    imp = step('impact figures', impact_figures)
    archive = step('archive count', archive_count)
    gh = step('github', github)
    evs = step('events', events)
    vids = step('youtube', youtube)

    if feed and imp and archive:
        posts, shorts = feed
        doc = put_block(doc, 'stats', r_stats(imp, archive + len(posts), shorts))
        doc = put_block(doc, 'blog', r_blog(posts, archive, shorts))
        doc = put_value(doc, 'articles_total', archive + len(posts))
        doc = put_value(doc, 'shorts', shorts)
        if gh:
            doc = put_block(doc, 'impact', r_impact(imp, archive, len(posts), gh))
    if gh:
        doc = put_block(doc, 'opensource', r_opensource(gh))
    if evs:
        doc = put_block(doc, 'events', r_events(evs))
    if vids:
        doc = put_block(doc, 'youtube', r_youtube(vids))

    if doc != before:
        doc = re.sub(r'"dateModified": "[\d-]+"', f'"dateModified": "{TODAY}"', doc)
        doc = re.sub(r'(Updated <time datetime=")[\d-]+(">)[^<]+(</time></span>)', rf'\g<1>{TODAY}\g<2>{nice_date(TODAY)}\3', doc)
        open(INDEX, 'w', encoding='utf-8').write(doc)
        sm = os.path.join(ROOT, 'sitemap.xml')
        s = open(sm, encoding='utf-8').read()
        open(sm, 'w', encoding='utf-8').write(re.sub(r'<lastmod>[\d-]+</lastmod>', f'<lastmod>{TODAY}</lastmod>', s))
        print('index.html refreshed')
    else:
        print('no changes')
    for w in warnings:
        print('warning:', w, file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
