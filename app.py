import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from classifier import suggest_placement
from graph_service import (
    GraphConflictError,
    GraphInputError,
    GraphItemNotFoundError,
    add_edge as create_edge_in_graph,
    add_node as create_node_in_graph,
    delete_edge as remove_edge_from_graph,
    delete_node as remove_node_from_graph,
    new_graph,
    update_edge as update_edge_in_graph,
    update_node as update_node_in_graph,
)
from graph_store import GraphAlreadyExistsError, GraphNotFoundError, GraphStore

app = Flask(__name__)
app.config["GRAPH_DATA_DIR"] = os.environ.get(
    "GRAPH_DATA_DIR", str(Path(__file__).resolve().parent / "graphs")
)
app.config["GRAPH_STARTER_DIR"] = str(Path(__file__).resolve().parent / "graph_starters")
app.config["DEFAULT_GRAPH_ID"] = "industrial-digital-systems"


def graph_store():
    return GraphStore(app.config["GRAPH_DATA_DIR"], app.config["GRAPH_STARTER_DIR"])


def load_graph(graph_id=None):
    return graph_store().load(graph_id or app.config["DEFAULT_GRAPH_ID"])


def save_graph(graph_id, data):
    graph_store().save(graph_id, data)


@app.errorhandler(GraphNotFoundError)
def graph_not_found(error):
    return jsonify({"error": f"graph not found: {error}"}), 404


@app.errorhandler(GraphItemNotFoundError)
def item_not_found(error):
    return jsonify({"error": str(error)}), 404


@app.errorhandler(GraphInputError)
def invalid_input(error):
    return jsonify({"error": str(error)}), 400


@app.errorhandler(GraphConflictError)
@app.errorhandler(GraphAlreadyExistsError)
def conflict(error):
    return jsonify({"error": str(error)}), 409


def request_data():
    body = request.get_json(force=True, silent=True)
    if not isinstance(body, dict):
        raise GraphInputError("JSON object required")
    return body


@app.get("/")
def index():
    return render_template("index.html", default_graph_id=app.config["DEFAULT_GRAPH_ID"])

@app.get("/api/graph")
@app.get("/api/graphs/<graph_id>")
def get_graph(graph_id=None):
    return jsonify(load_graph(graph_id))


@app.get("/api/graphs")
def get_graphs():
    return jsonify({"graphs": graph_store().list()})


@app.post("/api/graphs")
def create_graph():
    graph = new_graph(request_data())
    graph_store().create(graph)
    return jsonify({"id": graph["id"], "title": graph["title"]}), 201


@app.post("/api/graphs/<graph_id>/reset")
def reset_graph(graph_id):
    restored, backup = graph_store().reset(graph_id)
    return jsonify({"id": restored["id"], "backup": backup,
                    "nodes": len(restored["nodes"]), "edges": len(restored["edges"])})


@app.post("/api/add")
@app.post("/api/graphs/<graph_id>/nodes")
def add_node(graph_id=None):
    graph = load_graph(graph_id)
    node = create_node_in_graph(graph, request_data())
    save_graph(graph["id"], graph)
    return jsonify({"ok": True, "id": node["id"]})


@app.patch("/api/graphs/<graph_id>/nodes/<node_id>")
def update_node(graph_id, node_id):
    graph = load_graph(graph_id)
    node = update_node_in_graph(graph, node_id, request_data())
    save_graph(graph_id, graph)
    return jsonify({"node": node})


@app.delete("/api/graphs/<graph_id>/nodes/<node_id>")
def delete_node(graph_id, node_id):
    graph = load_graph(graph_id)
    removed_edges = remove_node_from_graph(graph, node_id)
    save_graph(graph_id, graph)
    return jsonify({"ok": True, "removed_edges": removed_edges})


@app.post("/api/graphs/<graph_id>/edges")
def add_edge(graph_id):
    graph = load_graph(graph_id)
    edge = create_edge_in_graph(graph, request_data())
    save_graph(graph_id, graph)
    return jsonify({"edge": edge}), 201


@app.patch("/api/graphs/<graph_id>/edges/<edge_id>")
def update_edge(graph_id, edge_id):
    graph = load_graph(graph_id)
    edge = update_edge_in_graph(graph, edge_id, request_data())
    save_graph(graph_id, graph)
    return jsonify({"edge": edge})


@app.delete("/api/graphs/<graph_id>/edges/<edge_id>")
def delete_edge(graph_id, edge_id):
    graph = load_graph(graph_id)
    remove_edge_from_graph(graph, edge_id)
    save_graph(graph_id, graph)
    return jsonify({"ok": True})

@app.post("/api/classify")
@app.post("/api/graphs/<graph_id>/classify")
def classify(graph_id=None):
    body = request_data()
    if any(not isinstance(body.get(key, ""), str) for key in ("term", "description")):
        raise GraphInputError("term and description must be strings")
    term = body.get("term", "").strip()
    description = body.get("description", "").strip()
    if not term:
        raise GraphInputError("term required")
    graph = load_graph(graph_id)
    return jsonify(suggest_placement(graph, term, description, os.environ.get("OPENAI_API_KEY")))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=True)
