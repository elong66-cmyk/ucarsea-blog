# UCarsea Insights

Static SEO content site for [ucarsea.com](https://ucarsea.com) — built with [Astro](https://astro.build) + deployed on [Cloudflare Pages](https://pages.cloudflare.com).

Lives at: **https://blog.ucarsea.com/**

## Quick start

```bash
npm install
npm run dev      # http://localhost:4321
npm run build    # static output → ./dist
```

## Adding a new article

1. Create `src/content/blog/<slug>.md`
2. Frontmatter:

```yaml
---
title: "Article title"
description: "Meta description, 140-160 chars."
pubDate: 2026-05-09
category: Laos    # Laos | Cambodia | Policy | Pricing | Logistics | Inspection | Insights
tags:
  - laos
  - "2025"        # quote numeric strings
keywords:
  - target keyword 1
  - target keyword 2
---
```

3. Write the article body in Markdown.
4. `git push` → Cloudflare Pages auto-builds and deploys (~30 seconds).

Optional: `updatedDate`, `heroImage`, `draft: true`.

## Architecture

```
src/
├── content/blog/            # Markdown articles
├── content.config.ts        # Schema validator
├── layouts/BaseLayout.astro # SEO meta, JSON-LD, nav, footer
├── components/              # Nav, Footer, ArticleCTA
├── pages/
│   ├── index.astro          # Article list
│   ├── blog/[...slug].astro # Single article
│   └── rss.xml.ts           # RSS feed
└── styles/global.css        # Dark + orange theme
```

## Deployment (Cloudflare Pages)

- Build command: `npm run build`
- Build output: `dist`
- Node: `22.12.0+`
- Custom domain: `blog.ucarsea.com`

## SEO

- [x] Sitemap → `/sitemap-index.xml`
- [x] RSS → `/rss.xml`
- [x] Open Graph + Twitter Card meta
- [x] Article JSON-LD per post
- [x] Organization JSON-LD on every page
- [x] Canonical URLs
- [x] `robots.txt` allow-all
- [x] Mobile-first
- [x] Zero-JS for content rendering (best CWV)
