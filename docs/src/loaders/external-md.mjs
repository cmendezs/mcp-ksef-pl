// Astro Content Layer loader that renders this package's existing Markdown files directly —
// README.md, CHANGELOG.md, CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, docs/TOOLS.md —
// with no copying, no splitting into pieces, and no separate content to keep in sync. Every
// page on the docs site is the real file, read fresh at every build. See
// context-library/templates/docs-site-template.md's "Content sourcing" section for why this
// replaced an earlier design that hand-copied README sections into separate page files.
//
// Starlight's docsSchema() requires a `title` in frontmatter; none of the source files have
// front matter at all. This loader derives `title` from the file's own leading `# ` heading
// (falling back to the entry `id` if no heading is found) and strips that heading from the
// rendered body so the page doesn't show it twice — Starlight already renders an <h1> from
// the derived title.
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

function extractTitle(raw, fallback) {
  const m = raw.match(/^#\s+(.+)$/m);
  return m ? m[1].trim() : fallback;
}

function stripLeadingH1(raw) {
  return raw.replace(/^#\s+.*\r?\n+/, "");
}

/**
 * @param {{ id: string, path: string, title?: string }[]} entries
 *   `path` is resolved relative to the Astro project root (this package's `docs/` directory),
 *   e.g. `"../README.md"` for a file at the package root, `"TOOLS.md"` for a file already
 *   inside `docs/`. A locale's homepage uses the bare locale code as `id` (e.g. `"fr"` for
 *   `README.fr.md`) — that is the one Starlight-recognized special case where an index-like
 *   page's `id` is not `"<locale>/<slug>"`. A missing file is skipped with a warning, not an
 *   error, so a package that lacks one of these (e.g. no RELEASE.md) does not fail the build —
 *   just omit that entry (and its sidebar link) for that package instead of leaving a dangling
 *   reference.
 */
export function externalMarkdown(entries) {
  return {
    name: "external-markdown-loader",
    load: async ({ config, store, parseData, renderMarkdown, generateDigest, logger }) => {
      for (const { id, path, title: titleOverride } of entries) {
        const fileUrl = new URL(path, config.root);
        if (!existsSync(fileUrl)) {
          logger.warn(`External markdown source not found for "${id}": ${path}`);
          continue;
        }
        const raw = readFileSync(fileUrl, "utf-8");
        const body = stripLeadingH1(raw);
        const data = { title: titleOverride ?? extractTitle(raw, id) };
        const parsedData = await parseData({ id, data, filePath: fileURLToPath(fileUrl) });
        const rendered = await renderMarkdown(body);
        const digest = generateDigest(raw);
        store.set({ id, data: parsedData, body, filePath: path, digest, rendered });
      }
    },
  };
}
