# tools/

`build.py` refreshes the live-data blocks in `../index.html` — stats, impact,
latest blog posts, YouTube videos, open source, events — from public sources
(blog.msdevbuild.com RSS, the blog repo's config and events, the msdevbuild.com
Blogger feed, the GitHub API and the YouTube channel feed).

```bash
python3 tools/build.py
```

Standard library only. It rewrites content between `<!-- data:NAME -->` and
`<!-- /data:NAME -->`, and values in `<span data-k="NAME">`. Everything else
in `index.html` is hand-edited. A source that fails leaves its block as it was.

`.github/workflows/refresh-data.yml` runs it daily and commits any change.
