import { defineCollection } from "astro:content";
import { docsSchema } from "@astrojs/starlight/schema";
import { externalMarkdown } from "./loaders/external-md.mjs";

export const collections = {
  docs: defineCollection({
    loader: externalMarkdown([
      { id: "index", path: "../README.md" },
      { id: "pl", path: "../README.pl.md" },
      { id: "changelog", path: "../CHANGELOG.md" },
      { id: "tools", path: "TOOLS.md" },
      { id: "contributing", path: "../CONTRIBUTING.md" },
      { id: "security", path: "../SECURITY.md" },
      { id: "code-of-conduct", path: "../CODE_OF_CONDUCT.md" },
    ]),
    schema: docsSchema(),
  }),
};
