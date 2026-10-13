"""Validate and store independent JSON knowledge graphs."""

import copy
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


SCHEMA_VERSION = 1
GRAPH_ID_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class GraphValidationError(ValueError):
    """A graph does not match the supported JSON format."""


class GraphNotFoundError(FileNotFoundError):
    """No graph exists with the requested ID."""


class GraphAlreadyExistsError(FileExistsError):
    """A graph with this ID already exists."""


def _required_text(item, key, context):
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GraphValidationError(f"{context}.{key} must be a non-empty string")
    return value


def _normalized_hint_term(value):
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def validate_graph(graph):
    if not isinstance(graph, dict):
        raise GraphValidationError("graph must be a JSON object")
    graph_id = _required_text(graph, "id", "graph")
    if not GRAPH_ID_PATTERN.fullmatch(graph_id):
        raise GraphValidationError("graph.id must be a lowercase hyphenated ID")
    _required_text(graph, "title", "graph")
    if not isinstance(graph.get("description"), str):
        raise GraphValidationError("graph.description must be a string")
    if type(graph.get("schema_version")) is not int or graph["schema_version"] != SCHEMA_VERSION:
        raise GraphValidationError(f"graph.schema_version must be {SCHEMA_VERSION}")
    if "starter_kind" in graph and graph["starter_kind"] != "empty":
        raise GraphValidationError("graph.starter_kind must be empty")
    if "display_layout" in graph and (
        not isinstance(graph["display_layout"], str)
        or graph["display_layout"] not in {"force", "hierarchical"}
    ):
        raise GraphValidationError("graph.display_layout must be force or hierarchical")
    if "color_by" in graph and (
        not isinstance(graph["color_by"], str)
        or graph["color_by"] not in {"type", "layer"}
    ):
        raise GraphValidationError("graph.color_by must be type or layer")
    if "discovery_mode" in graph and type(graph["discovery_mode"]) is not bool:
        raise GraphValidationError("graph.discovery_mode must be a boolean")
    if not isinstance(graph.get("nodes"), list):
        raise GraphValidationError("graph.nodes must be a list")
    if not isinstance(graph.get("edges"), list):
        raise GraphValidationError("graph.edges must be a list")

    node_ids = set()
    node_types = set()
    for index, node in enumerate(graph["nodes"]):
        context = f"nodes[{index}]"
        if not isinstance(node, dict):
            raise GraphValidationError(f"{context} must be an object")
        node_id = _required_text(node, "id", context)
        _required_text(node, "label", context)
        node_types.add(_required_text(node, "type", context))
        for key in ("layer", "description"):
            if key in node and not isinstance(node[key], str):
                raise GraphValidationError(f"{context}.{key} must be a string")
        if "url" in node:
            url = node["url"]
            if not isinstance(url, str) or not url.strip():
                raise GraphValidationError(f"{context}.url must be a non-empty HTTPS URL")
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.netloc:
                raise GraphValidationError(f"{context}.url must be a non-empty HTTPS URL")
        if node_id in node_ids:
            raise GraphValidationError(f"duplicate node id: {node_id}")
        node_ids.add(node_id)

    if "initial_type_filter" in graph and (
        not isinstance(graph["initial_type_filter"], str)
        or graph["initial_type_filter"] not in node_types
    ):
        raise GraphValidationError("graph.initial_type_filter must name a node type")

    edge_ids = set()
    for index, edge in enumerate(graph["edges"]):
        context = f"edges[{index}]"
        if not isinstance(edge, dict):
            raise GraphValidationError(f"{context} must be an object")
        edge_id = _required_text(edge, "id", context)
        source = _required_text(edge, "source", context)
        target = _required_text(edge, "target", context)
        _required_text(edge, "relation", context)
        if edge_id in edge_ids:
            raise GraphValidationError(f"duplicate edge id: {edge_id}")
        if edge_id in node_ids:
            raise GraphValidationError(f"edge id conflicts with node id: {edge_id}")
        edge_ids.add(edge_id)
        if source not in node_ids or target not in node_ids:
            raise GraphValidationError(
                f"{context} refers to an unknown node: {source} -> {target}"
            )

    fallback = graph.get("placement_hint_fallback")
    if fallback is not None:
        if not isinstance(fallback, dict):
            raise GraphValidationError("graph.placement_hint_fallback must be an object")
        for key in ("parent", "relation", "reason"):
            _required_text(fallback, key, "placement_hint_fallback")

    hints = graph.get("placement_hints", [])
    if not isinstance(hints, list):
        raise GraphValidationError("graph.placement_hints must be a list")
    hint_terms = set()
    for index, hint in enumerate(hints):
        context = f"placement_hints[{index}]"
        if not isinstance(hint, dict):
            raise GraphValidationError(f"{context} must be an object")
        term = _required_text(hint, "term", context)
        for key in ("parent", "relation", "type", "reason"):
            _required_text(hint, key, context)
        if "layer" in hint:
            _required_text(hint, "layer", context)
        aliases = hint.get("aliases", [])
        if not isinstance(aliases, list):
            raise GraphValidationError(f"{context}.aliases must be a list")
        for name in [term, *aliases]:
            if not isinstance(name, str) or not name.strip():
                raise GraphValidationError(f"{context}.aliases must contain non-empty strings")
            normalized = _normalized_hint_term(name)
            if not normalized:
                raise GraphValidationError(f"{context}.aliases must contain letters or digits")
            if normalized in hint_terms:
                raise GraphValidationError(f"duplicate placement hint: {normalized}")
            hint_terms.add(normalized)
        alternates = hint.get("alternates", [])
        if not isinstance(alternates, list):
            raise GraphValidationError(f"{context}.alternates must be a list")
        parents = {hint["parent"]}
        for alternate_index, alternate in enumerate(alternates):
            alternate_context = f"{context}.alternates[{alternate_index}]"
            if not isinstance(alternate, dict):
                raise GraphValidationError(f"{alternate_context} must be an object")
            parent = _required_text(alternate, "parent", alternate_context)
            _required_text(alternate, "relation", alternate_context)
            if "reason" in alternate:
                _required_text(alternate, "reason", alternate_context)
            if parent in parents:
                raise GraphValidationError(f"duplicate placement parent: {parent}")
            parents.add(parent)


def load_graph(path):
    with open(path, "r", encoding="utf-8") as file:
        graph = json.load(file)
    validate_graph(graph)
    return graph


def save_graph(path, graph):
    validate_graph(graph)
    path = Path(path)
    temporary_path = None
    try:
        # The temporary file must be beside the graph for os.replace to be atomic.
        descriptor, name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary_path = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(graph, file, indent=2, ensure_ascii=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


class GraphStore:
    def __init__(self, directory, starter_directory=None):
        self.directory = Path(directory)
        self.starter_directory = Path(starter_directory) if starter_directory else (
            Path(__file__).resolve().parent / "graph_starters"
        )

    def _path(self, graph_id):
        if not isinstance(graph_id, str) or not GRAPH_ID_PATTERN.fullmatch(graph_id):
            raise GraphNotFoundError(graph_id)
        return self.directory / f"{graph_id}.json"

    def list(self):
        graphs = []
        for path in sorted(self.directory.glob("*.json")):
            graph = load_graph(path)
            if path.stem != graph["id"]:
                raise GraphValidationError(f"{path.name} does not match graph.id")
            graphs.append({
                "id": graph["id"],
                "title": graph["title"],
                "description": graph["description"],
            })
        return graphs

    def load(self, graph_id):
        path = self._path(graph_id)
        try:
            graph = load_graph(path)
        except FileNotFoundError as error:
            raise GraphNotFoundError(graph_id) from error
        if graph["id"] != graph_id:
            raise GraphValidationError(f"{path.name} does not match graph.id")
        return graph

    def save(self, graph_id, graph):
        path = self._path(graph_id)
        validate_graph(graph)
        if graph["id"] != graph_id:
            raise GraphValidationError("graph.id does not match the requested ID")
        save_graph(path, graph)

    def create(self, graph):
        validate_graph(graph)
        path = self._path(graph["id"])
        if path.exists():
            raise GraphAlreadyExistsError(f"graph already exists: {graph['id']}")
        save_graph(path, graph)

    def reset(self, graph_id):
        current = self.load(graph_id)
        starter_path = self.starter_directory / f"{graph_id}.json"
        if current.get("starter_kind") != "empty" and starter_path.is_file():
            starter = load_graph(starter_path)
            if starter["id"] != graph_id:
                raise GraphValidationError("starter graph ID does not match")
        else:
            starter = copy.deepcopy(current)
            starter["nodes"] = []
            starter["edges"] = []

        backup_directory = self.directory / ".backups"
        backup_directory.mkdir(exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup_path = backup_directory / f"{graph_id}-{timestamp}.json"
        save_graph(backup_path, current)
        self.save(graph_id, starter)
        return starter, backup_path.relative_to(self.directory).as_posix()
