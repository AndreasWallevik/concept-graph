"""Small, in-memory operations on one knowledge graph."""

import re

from graph_store import GRAPH_ID_PATTERN, SCHEMA_VERSION


class GraphInputError(ValueError):
    """A requested graph change has invalid fields or references."""


class GraphItemNotFoundError(LookupError):
    """A node or relationship does not exist in this graph."""


class GraphConflictError(ValueError):
    """A requested graph change duplicates something already present."""


def _text(data, key, default=None, allow_blank=False):
    value = data.get(key, default)
    if not isinstance(value, str):
        raise GraphInputError(f"{key} must be a string")
    value = value.strip()
    if not value and not allow_blank:
        raise GraphInputError(f"{key} required")
    return value


def _only_fields(data, allowed):
    extra = set(data) - allowed
    if extra:
        raise GraphInputError(f"unsupported field: {sorted(extra)[0]}")


def _slug(value, fallback):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or fallback


def _unique_id(base, graph):
    used = {item["id"] for item in graph["nodes"] + graph["edges"]}
    candidate = base
    number = 2
    while candidate in used:
        candidate = f"{base}-{number}"
        number += 1
    return candidate


def _find(items, item_id, kind):
    for item in items:
        if item["id"] == item_id:
            return item
    raise GraphItemNotFoundError(f"{kind} not found: {item_id}")


def _node_ids(graph):
    return {node["id"] for node in graph["nodes"]}


def new_graph(data):
    _only_fields(data, {"id", "title", "description"})
    title = _text(data, "title")
    graph_id = _text(data, "id", _slug(title, "graph"))
    if not GRAPH_ID_PATTERN.fullmatch(graph_id):
        raise GraphInputError("id must use lowercase letters, digits, and hyphens")
    return {
        "schema_version": SCHEMA_VERSION,
        "starter_kind": "empty",
        "id": graph_id,
        "title": title,
        "description": _text(data, "description", "", allow_blank=True),
        "nodes": [],
        "edges": [],
    }


def add_node(graph, data):
    _only_fields(data, {"label", "description", "type", "layer", "parent", "relation"})
    label = _text(data, "label")
    parent = _text(data, "parent", "", allow_blank=True)
    relation = _text(data, "relation", "contains") if parent else None
    if parent and parent not in _node_ids(graph):
        raise GraphInputError("parent must be an existing node")
    node = {
        "id": _unique_id(_slug(label, "node"), graph),
        "label": label,
        "type": _text(data, "type", "concept"),
        "layer": _text(data, "layer", "Custom", allow_blank=True),
        "description": _text(data, "description", "", allow_blank=True),
    }
    graph["nodes"].append(node)
    if parent:
        add_edge(graph, {"source": parent, "target": node["id"], "relation": relation})
    return node


def update_node(graph, node_id, data):
    _only_fields(data, {"label", "description", "type", "layer"})
    if not data:
        raise GraphInputError("at least one node field required")
    node = _find(graph["nodes"], node_id, "node")
    for key in data:
        node[key] = _text(data, key, allow_blank=key in {"description", "layer"})
    return node


def delete_node(graph, node_id):
    _find(graph["nodes"], node_id, "node")
    graph["nodes"] = [node for node in graph["nodes"] if node["id"] != node_id]
    before = len(graph["edges"])
    graph["edges"] = [
        edge for edge in graph["edges"]
        if edge["source"] != node_id and edge["target"] != node_id
    ]
    return before - len(graph["edges"])


def _validate_edge(graph, source, target, relation, excluding=None):
    node_ids = _node_ids(graph)
    if source not in node_ids or target not in node_ids:
        raise GraphInputError("source and target must be existing nodes")
    if any(
        edge["id"] != excluding
        and edge["source"] == source
        and edge["target"] == target
        and edge["relation"] == relation
        for edge in graph["edges"]
    ):
        raise GraphConflictError("relationship already exists")


def add_edge(graph, data):
    _only_fields(data, {"source", "target", "relation"})
    source = _text(data, "source")
    target = _text(data, "target")
    relation = _text(data, "relation")
    _validate_edge(graph, source, target, relation)
    edge = {
        "id": _unique_id(f"edge-{source}-{target}", graph),
        "source": source,
        "target": target,
        "relation": relation,
    }
    graph["edges"].append(edge)
    return edge


def update_edge(graph, edge_id, data):
    _only_fields(data, {"source", "target", "relation"})
    if not data:
        raise GraphInputError("at least one relationship field required")
    edge = _find(graph["edges"], edge_id, "relationship")
    source = _text(data, "source", edge["source"])
    target = _text(data, "target", edge["target"])
    relation = _text(data, "relation", edge["relation"])
    _validate_edge(graph, source, target, relation, excluding=edge_id)
    edge.update(source=source, target=target, relation=relation)
    return edge


def delete_edge(graph, edge_id):
    _find(graph["edges"], edge_id, "relationship")
    graph["edges"] = [edge for edge in graph["edges"] if edge["id"] != edge_id]
