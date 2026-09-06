import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import starlightLlmsTxt from "starlight-llms-txt";

export default defineConfig({
  site: "https://cmendezs.github.io",
  base: "/mcp-ksef-pl/",
  integrations: [
    starlight({
      title: "mcp-ksef-pl",
      description: "MCP server for Polish electronic invoicing — KSeF FA(3)/FA(2) and Peppol BIS 3.0/EN 16931",
      customCss: ["./src/styles/docs-theme.css"],
      social: [
        { icon: "github", label: "GitHub", href: "https://github.com/cmendezs/mcp-ksef-pl" },
      ],
      locales: {
        root: { label: "English", lang: "en" },
        pl: { label: "Polski", lang: "pl" },
      },
      sidebar: [
        { label: "Overview", link: "/" },
        { label: "Tools", link: "/tools/" },
        { label: "Changelog", link: "/changelog/" },
        { label: "Contributing", link: "/contributing/" },
        { label: "Security", link: "/security/" },
        { label: "Code of Conduct", link: "/code-of-conduct/" },
      ],
      plugins: [
        starlightLlmsTxt({
          projectName: "mcp-ksef-pl",
          description: "MCP server for Polish electronic invoicing — KSeF FA(3)/FA(2) and Peppol BIS 3.0/EN 16931",
          customSets: [
            {
              label: "Key links",
              description: "PyPI and MCP registry entries",
              links: ["https://pypi.org/project/mcp-ksef-pl/", "https://registry.modelcontextprotocol.io/v0/servers?search=io.github.cmendezs/mcp-ksef-pl"],
            },
          ],
        }),
      ],
    }),
  ],
});
