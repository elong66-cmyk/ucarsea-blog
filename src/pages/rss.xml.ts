import rss from "@astrojs/rss";
import { getCollection } from "astro:content";
import type { APIContext } from "astro";

export async function GET(context: APIContext) {
  const posts = await getCollection("blog", ({ data }) => !data.draft);
  return rss({
    title: "UCarsea Insights",
    description:
      "Cross-border used car trade insights — policy, costs, and logistics from active UCarsea operations.",
    site: context.site!,
    items: posts
      .sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf())
      .map((p) => ({
        title: p.data.title,
        description: p.data.description,
        pubDate: p.data.pubDate,
        link: `/${p.id}/`,
        categories: [p.data.category, ...p.data.tags],
      })),
    customData: `<language>en-us</language>`,
  });
}
