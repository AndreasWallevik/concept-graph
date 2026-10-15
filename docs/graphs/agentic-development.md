# Reading guide: AI, MCP, and agentic development

**Status:** Learning graph, not an integration or a security policy  
**Last reviewed:** 14 October 2026  
**Graph:** [`graphs/agentic-development.json`](../../graphs/agentic-development.json)  
**Open in the local app:** `http://127.0.0.1:5050/?graph=agentic-development`

## How to explore the graph

The graph has seven domains. Select one in **All domains** to focus on a smaller part of the map, or search for a concept. Read an arrow as `source —relationship→ target`. The `covers` relationships power the domain filter. Select a node to see its description and direct connections. **Reset current graph** restores the starter in `graph_starters/` after saving a backup.

| Domain | Starting path | What it explains |
| --- | --- | --- |
| AI and Models | Large Language Model → Context Window → Tool Calling | What a model can propose and how context affects its output. |
| Agents and Tools | AI Agent → Agent Loop → Harness | Which component actually executes file edits and API calls. |
| MCP and Integration | MCP Host → Client → Server → Tool | How capabilities reach AI applications through a shared protocol. |
| Agentic Development | Planning → Implementation → Tests → Diff → Code Review | A development workflow with human oversight. |
| Security and Trust | Untrusted Tool Result → Prompt Injection | Why content, credentials, and actions need separate trust boundaries. |
| Jev and Decisions | Jev → Choice / Score / Noul → Decision Policy | Structured judgments and routing under uncertainty. |
| Quality and Operations | Tracing → Evaluations → Regression Checks | How to detect failures and measure improvement over time. |

## The foundation from Claude's explanation

The explanation of built-in tools, MCP, and live systems is a useful starting point. A model proposes a tool call; the host application executes it and returns the result. Built-in file and shell tools can be enough for local repository work. MCP provides a common client/server interface for additional capabilities. Its core server primitives are **tools, resources, and prompts**, and a server can run locally or remotely. [MCP architecture](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture), [MCP server features](https://modelcontextprotocol.io/specification/2026-07-28/server/index).

Two security qualifications matter:

1. MCP makes capabilities discoverable, but **the protocol alone does not guarantee** that credentials are hidden from the model, that every tool has narrow permissions, or that actions require approval and are logged. Those properties depend on the host, server, runtime, and access configuration. Agent-generated code can reach the files, credentials, and network available to its environment. [OpenAI Docs: sandbox security](https://developers.openai.com/api/docs/guides/agents-api/environments/security), [OpenAI Docs: guardrails and human review](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals).
2. A file edit can later affect production through a build, CI/CD pipeline, or deployment. The distinction between an artifact and a live system concerns *when and where* its effects occur; writing a file is not always low risk.

“REST parity” is a design choice for a particular MCP server, not a requirement of MCP. A task-shaped tool such as `get_alarm_history(area)` can be narrower and easier to use than exposing every REST endpoint. A shell script or CLI that calls the same API is also a valid option when the runtime and controls fit the task.

## Additional concepts in this graph

The graph adds context windows, RAG, embeddings, and structured output; agent loops, harnesses, memory, and multi-agent work; skills, planning, code review, and CI/CD; and tracing, evals, datasets, retries, idempotency, and cost limits. Each affects the quality or security of a real agent workflow. [OpenAI Docs: agents](https://developers.openai.com/api/docs/guides/agents), [OpenAI Docs: agent evaluations](https://developers.openai.com/api/docs/guides/agent-evals).

One useful route through the graph is:

```text
LLM → Tool Calling → Harness → Built-in Tools → Repository → CI/CD
                              ↘ MCP Host → MCP Client → MCP Server → Live System
```

Another route shows an attack path and the controls around it:

```text
External document or API response → Untrusted Tool Result → Prompt Injection
                                                       → Misused Tool → Data Exfiltration

Trust Boundary + Least Privilege + Authorization + Outbound Network Controls
```

Prompt injection can arrive through documents, web pages, repository files, or tool results. A stronger prompt alone is not a sufficient control. The system that executes a tool must validate arguments and enforce permissions, and sensitive actions may require human approval. OWASP identifies agent goal hijacking, tool misuse, and identity or privilege abuse among central agentic risks. [OWASP Top 10 for Agentic Applications](https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/).

The examples **read product data**, **read a tag value**, and **acknowledge an alarm** illustrate different control needs. Reads should be limited to necessary data. Acknowledging an alarm changes state in an operations system and requires specific authorization and an audit trail. This graph only explains these operations; it connects to no CRM or OT system.

## What “Jev” means here

Here Jev means **TypeSafe AI's Jev model**. It is a specialized model for typed judgments, not a generic term for AI agents and not part of the MCP standard. TypeSafe documents three question types: **Choice** selects among defined alternatives, **Score** assesses ordered levels, and **Noul** returns a 0–1 value for a yes/no question. Choice and Score also return a separate `confidence` value; Noul does not. [TypeSafe: introduction](https://docs.typesafe.ai/introduction), [TypeSafe: primitives](https://docs.typesafe.ai/primitives).

One possible place for Jev in an agent workflow is to suggest routing or assess a narrow question while ordinary code determines permitted actions. An unclear or low-confidence result can lead to more information, another method, or human review. **Confidence summarizes the model's probability distribution; it does not prove that an individual answer is correct.** Test thresholds on representative data and account for the consequences of mistakes. [TypeSafe: confidence](https://docs.typesafe.ai/confidence). This project does not install or call Jev.

## Maintenance

Concepts and product capabilities change. Review definitions and source links before using this graph for training or decisions. MCP and OpenAI descriptions use official documentation, and the Jev section uses TypeSafe's documentation. Keep **protocols**, **products**, **patterns**, **risks**, and **controls** distinct so a product claim is not mistaken for a general standard.
