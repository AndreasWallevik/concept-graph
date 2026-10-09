# Industrial Knowledge Graph

A small local knowledge graph for industrial automation + software engineering.

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
```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5050

## AI placement
The app works without an API key using a simple local rule-based fallback.

For AI classification:
```powershell
$env:OPENAI_API_KEY="your-key"
python app.py
```

The API key stays server-side in the environment and is never placed in browser JavaScript.

## Data model
All concepts and relationships live in `graph_data.json`.

This is intentionally a graph rather than a strict tree: industrial terms overlap. For example,
Ignition can participate in SCADA, historian, MES integration and DataOps, while MQTT is both an
integration technology and a common building block in a UNS.

## Suggested next step
Add persistent edit/delete, aliases/synonyms, sources/links, and multiple parent relationships.
