# Concept Graph

A small local knowledge graph app. Its current graph is **Industrial & Digital Systems**,
covering industrial automation, software engineering, data, security, and AI.

## What it covers
- ISA-95 / Purdue-style business & control layers
- ERP, MES/MOM, SCADA/HMI, PLC/DCS/RTU, sensors/actuators
- DataOps / Industrial DataOps, ETL, contextualization, UNS, MQTT, Sparkplug, OPC UA
- APIs, middleware, frontend/backend, microservices, event-driven architecture
- Git, CI/CD, Docker, Kubernetes, IaC, Ansible, observability, SRE
- IAM, IdP, RBAC, MFA, secrets, segmentation, industrial DMZ
- LLMs, agents, MCP, RAG, embeddings, prompt injection and token/context concepts
- Example platforms: Ignition, Perspective, HighByte, React, Kepware

## Run
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5050

By default the app reads and writes graph files in `graphs/`. To use another
directory, set `GRAPH_DATA_DIR` before starting Flask:

```powershell
$env:GRAPH_DATA_DIR="C:\path\to\graphs"
python app.py
```

`GRAPH_DATA_DIR` replaces the single-graph `GRAPH_DATA_PATH` setting from step 1.
The directory must already exist. The current page opens
`industrial-digital-systems` by default. Use the **Graph** selector to switch
between Industrial & Digital Systems, Ignition Core Training, ISA-95 & Purdue
Model, Security & Networking, and Autic Product Graph. The URL keeps
the selected graph as `?graph=<id>`, so it can be bookmarked.

## ISA-95 & Purdue Model

Select **ISA-95 & Purdue Model** in the graph menu, or open
`http://127.0.0.1:5050/?graph=isa95-purdue`. Its top-down layout shows two
connected views: ISA-95 functional Levels 4 through 0 and commonly used Purdue
network zones. Related branches cover the equipment hierarchy, resource and
process models, the four manufacturing operations areas, and information shared
between business planning and manufacturing operations. Example systems can
connect to both views: a controller may implement ISA-95 Level 2 control
activities while commonly residing in a Purdue Level 1 network zone.

This graph is a teaching overview of the models, not a claim that every product
has one fixed level. The Industrial DMZ is shown as a network boundary, not as
an additional ISA-95 functional level. The graph follows the
[ISA-95 overview](https://www.isa.org/standards-and-publications/isa-standards/isa-95-standard),
[ISA discussion of equipment and process segments](https://www.isa.org/intech/2020/september-october/the-isa-95-enterprise-control-system-integration-s),
and [NIST's OT security guide](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=956505).
**Reset current graph** restores this dedicated starter and backs up the
previous class state.

## Security & Networking

Select **Security & Networking**, or open
`http://127.0.0.1:5050/?graph=security-networking`. This independent graph has
132 concepts across 13 domains. Start with **Networking Fundamentals** and
follow **understand before** edges toward protocols, identity, cryptography,
security controls, OT, and governance. Other edges explain concrete mechanisms,
such as DHCP leasing an IP address and OIDC extending OAuth 2.0.

Use the **All domains** menu to focus on one domain. Its **covers** edges and
matching theme identify members; the filter also shows relationships between
concepts in that domain.
Search matches names and descriptions. Click a concept for its explanation,
and use **Reset current graph** to restore the starter after taking notes.
**UUID / GUID** is one identifier concept, not a security control. Terms such as
SFTP, SNMP, ABAC, and EDR can be added later; this initial graph prioritizes
the prerequisites and connections most useful for software and OT work.

The identity distinctions follow the [OAuth 2.0 framework](https://www.rfc-editor.org/info/rfc6749/),
[OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0-18.html),
and [JWT specification](https://www.rfc-editor.org/info/rfc7519/).
The OT and governance descriptions use the
[ISA-95 overview](https://www.isa.org/standards-and-publications/isa-standards/isa-95-standard),
[ISA/IEC 62443 overview](https://www.isa.org/standards-and-publications/isa-standards/isa-iec-62443-series-of-standards),
[NIS2 overview](https://digital-strategy.ec.europa.eu/en/policies/nis2-directive),
[GDPR text](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679),
[ISO/IEC 27001 overview](https://committee.iso.org/standard/27001),
and [NIST CSF 2.0](https://www.nist.gov/publications/nist-cybersecurity-framework-csf-20).

## Autic Product Graph

Select **Autic Product Graph**, or open
`http://127.0.0.1:5050/?graph=autic-products`. This proof of concept uses a
small, manually curated public-source dataset in `graphs/autic-products.json`.
Its reset seed is `graph_starters/autic-products.json`. Nodes represent products,
product families, manufacturers, categories, protocols, technologies,
applications and industries. Edges connect these concepts with directed,
explicit relations such as `SUPPORTS_PROTOCOL` and `USED_FOR`.

Search for a name such as **OPC UA** to see matching nodes and their immediate
connections. The **All types** menu focuses on one node type and its immediate
connections. Click a node to show only its direct relationships, and use the
sidebar's related-node list to move to a neighbour. The sidebar also shows the
node description and its original Autic source link. **Reset view** clears
search, type and selection focus; **Fit** adjusts the canvas. Relationship
labels appear when a node is selected, keeping the overview readable. The
graph opens with **product category** selected to keep the first view focused.
Choose **All types** or **Reset view** to show the whole sample. The
existing **Reset current graph** restores the curated starter after saving a
backup of any edits.

The seed covers Ignition, EXOR HMI, Red Lion gateways/networking, Opto 22
remote I/O, PiiGAB meter gateways and Accuenergy energy meters. Cross-portfolio
protocol links are grounded in Autic's public [Ignition SCADA](https://www.autic.no/ignition-scada-software/),
[eX700 series](https://www.autic.no/product-category/operatorpanel/exor-ex700/),
[DA10D](https://www.autic.no/en/product/da10d-protokollkonverter-og-iiot-enhet/),
[groov RIO](https://www.autic.no/en/product/groov-rio-med-2gb-ram-7gb-ssd-klargjort-for-ignition-edge/),
[PI900S HAN](https://www.autic.no/product/pi900s-han-adapter-2/), and
[energy meter](https://www.autic.no/product-category/strom/) pages. Capabilities
that need separate licences are noted in product descriptions. This is a
portfolio sample, not a complete product catalogue. A future external source
can output the same JSON schema without changing the Cytoscape UI.

The **Connect from** menu lists concepts in the selected graph. Adding a concept
stores it in that graph; choose **Standalone** for a concept without a connection.
Choose the directed relationship from the selected concept to the new concept.
**Suggest placement** fills in a proposed connection and type; review or change
them before clicking **Add to graph**. Suggestions never save anything on their own.
If the concept already exists without its suggested relationship, use
**Connect existing concept** to add that relationship without duplicating the node.
The **Theme or group** field sets a concept's color. The theme legend shows the
colors in the selected graph; arrows use the destination concept's color.
Suggestions inherit the connected concept's theme unless a placement hint names
a different one. Ignition and Gateway use the Platform theme; Designer uses
Design tools.

**Reset current graph** asks for confirmation, saves the current version in
`graphs/.backups/`, then restores a built-in graph from `graph_starters/`.
Graphs created in the app reset to an empty canvas while keeping their name and
description. With `GRAPH_DATA_DIR`, backups are saved in that directory's
`.backups/` folder. Restarting the app never resets a graph.

Use **New graph** to create an empty graph. Its ID is generated from the name
unless you supply one. Click a concept to edit or delete it; deleting a concept
also removes its connected relationships. Add a directed relationship by
choosing its source, relation, and target. Click a relationship to edit or delete
it. Relationship names appear on the graph.

`GET /api/graphs` lists available
graphs; `GET /api/graphs/<id>` returns one graph; and
`POST /api/graphs/<id>/nodes` adds a node to that graph. The existing
`/api/graph` and `/api/add` routes still use the default graph.
`POST /api/graphs` creates a graph. Node and edge changes use
`PATCH` and `DELETE` on `/api/graphs/<id>/nodes/<node-id>` and
`/api/graphs/<id>/edges/<edge-id>`; new edges use
`POST /api/graphs/<id>/edges`.
`POST /api/graphs/<id>/classify` suggests a placement within that graph;
`POST /api/classify` remains an alias for the default graph.
`POST /api/graphs/<id>/reset` saves a backup and resets only that graph.

Node and edge IDs must be unique within each graph, and every edge must refer
to nodes in that same graph. Saves write a temporary file beside the graph and
replace the old file once the new JSON is complete.

Run the baseline checks with `.venv\Scripts\python.exe -m unittest discover -s tests`.

## Placement suggestions
Without an API key, the app suggests connections using labels, descriptions,
and relationships in the selected graph. If there is no clear match, it suggests
adding a standalone concept. It also flags an exact match with an existing label.
Graphs can include optional `placement_hints` for terms whose relationship cannot
be inferred from labels alone. Ignition Core Training has hints for the major
topics in the Ignition 8.3 Core class, including devices and tags, Perspective,
security, alarming, history, Transaction Groups, reporting, Vision, and backups.
Hints use a more specific parent when that concept is present. For example,
**Flex Container** connects to **View** if it exists, then **Perspective** if
there is no View yet. If neither exists, the hint connects it broadly to
**Ignition**. Adding a parent later lets **Suggest placement** propose the
missing, more specific relationship for the existing concept. Common alternate
names and course chapter headings are recognized without regard to case, spaces,
or punctuation. Recognized aliases can also find an existing concept: entering
**Historian** finds an existing **Tag Historian** instead of suggesting a duplicate.
Ignition 8.3 distinguishes the **Historian Core module** from its **Core Historian**
storage provider. **SQL Historian** is another storage provider supplied by the
SQL Historian module. The history hints keep those roles separate, following the
official [Historian Core module](https://www.docs.inductiveautomation.com/docs/8.3/getting-started/modules-overview/core-modules/tag-historian-module)
and [history providers](https://www.docs.inductiveautomation.com/docs/8.3/ignition-modules/tag-historian/tag-history-providers) documentation.
Perspective is modeled as a visualization module hosted by the Gateway, following
the official [Ignition module overview](https://www.docs.inductiveautomation.com/docs/8.3/getting-started/modules-overview)
and [Perspective/Vision guide](https://docs.inductiveautomation.com/docs/8.3/getting-started/perspective-and-vision).
A hint suggests a connection; it never creates one on its own.

For AI classification:
```powershell
$env:OPENAI_API_KEY="your-key"
python app.py
```

With an API key, clicking **Suggest placement** sends the entered term and the
selected graph's concepts and relationships to OpenAI. The request disables
response storage with `store: false`. If the API is unavailable or its suggestion
does not reference this graph, the app uses the local suggestion. The API key
stays server-side in the environment and is never placed in browser JavaScript.

## Data model
Each graph is one JSON file in `graphs/`, named after its stable ID. The file
contains `schema_version`, `id`, `title`, `description`, `nodes`, and `edges`.
Edges have stable IDs and a free-text `relation`, such as `contains`, `runs on`,
or `configured by`. The title may change without changing the ID or filename.

The existing graph is `graphs/industrial-digital-systems.json`.
`graphs/ignition-core.json` contains the current class state. Its starter file
contains only Ignition, ready to grow during training. Other graphs can be added
as separate JSON files with the same fields and independent node IDs.
`graphs/isa95-purdue.json` is the working ISA-95/Purdue graph; its starter is in
`graph_starters/isa95-purdue.json`. Graphs may set `display_layout` to
`hierarchical` for a top-down view or omit it to use the force layout.
`graphs/security-networking.json` is the working security graph; its starter is
`graph_starters/security-networking.json`.

This is intentionally a graph rather than a strict tree: industrial terms overlap. For example,
Ignition can participate in SCADA, historian, MES integration and DataOps, while MQTT is both an
integration technology and a common building block in a UNS.
