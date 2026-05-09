// @ts-check
import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

// https://astro.build/config
export default defineConfig({
  site: "https://blog.ucarsea.com",
  trailingSlash: "always",
  build: {
    format: "directory",
  },
  integrations: [
    sitemap({
      changefreq: "weekly",
      priority: 0.7,
      filter: (page) => !page.includes("/draft/"),
    }),
  ],
  markdown: {
    shikiConfig: {
      theme: "github-dark-dimmed",
      wrap: true,
    },
  },
});
