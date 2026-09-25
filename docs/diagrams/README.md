# Editable architecture diagrams

[Documentation index](../README.md)

## Plain-language project guide

The separate [project guide](../project-guide.html) explains the plan in plain technical language, including historical/latest data, build order, tool roles and a proposed repository layout. Expand the folder explanations for detail. It is self-contained and works offline; the folder structure remains a proposal for feedback.

## Primary HTML architecture review

Open [UrbanFlow architecture review](architecture.html) directly in a browser. This adapts the supplied internal HTML, retaining its transit-map layout, clickable stations, path filters, one-trip walkthrough and review structure. It adds the reconciled eight-stage roadmap, historical/latest lifecycle, modular expansion boundaries and local resource policy. It is self-contained with no build step or external assets.

Use mouse or keyboard to open stations; Escape closes details and restores focus. On narrow screens the map scrolls horizontally. Edit the SVG, explanatory sections and `STATIONS` data together. Curated Markdown remains authoritative for implementation decisions. All capabilities remain planned.

## Preserved earlier System Atlas

The [earlier System Atlas](system-atlas.html) preserves the broader product/ML/agent view and searchable technology learning inventory. It is labelled as an earlier reference: priorities and roadmap details can predate the current reconciliation. Keep `assets/` beside it for bundled logos. It works offline and includes a print action.

Bundled logos come from [Simple Icons v16.0.0](https://github.com/simple-icons/simple-icons/tree/16.0.0), distributed under CC0. Brand marks remain the property of their respective owners. Components without bundled logos use text or symbolic marks.

## Draw.io source diagrams

These are native, uncompressed diagrams.net/draw.io XML files. Open a `.drawio` file in the desktop editor or import it into diagrams.net. Shapes, labels, connectors, and positions are editable; no images or external assets are required.

| Diagram                                 | View                                                                                      |
| --------------------------------------- | ----------------------------------------------------------------------------------------- |
| [Platform](platform.drawio)             | Sources, historical and streaming paths, lakehouse, serving, and control responsibilities |
| [ML and serving](ml-and-serving.drawio) | Training lifecycle, request routing, SQL guard, tools, and evidence                       |
| [Deployment](deployment.drawio)         | Local profiles, bounded public demo, and proposed production topology                     |

These broader reference diagrams retain the original ML/agent and deployment scope; the primary HTML and current Markdown explain the newer modelling, lifecycle and resource decisions. All diagrams show planned architecture. A solid connector follows the arrow's labeled relationship. Dashed connectors represent metadata/control relationships; dashed boxes identify optional or unresolved components. Platform data arrows show data/result movement; serving request arrows show calls. The deployment diagram compares tiers, rather than implying the tiers all operate simultaneously.

Implementation details and open choices live in the linked architecture documents. Keep diagrams and those documents aligned when decisions change.
