import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const blog = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/blog" }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    heroImage: z.string().optional(),
    category: z.enum(["Laos", "Cambodia", "Myanmar", "Vietnam", "UAE", "Central Asia", "Policy", "Pricing", "Logistics", "Inspection", "Insights"]),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
    keywords: z.array(z.string()).default([]),
  }),
});

export const collections = { blog };
