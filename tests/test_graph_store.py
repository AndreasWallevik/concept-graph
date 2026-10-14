import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app
from graph_store import (
    GraphNotFoundError, GraphStore, GraphValidationError,
    load_graph, save_graph, validate_graph,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH_ID = "industrial-digital-systems"
SOURCE_GRAPH = PROJECT_ROOT / "graphs" / f"{GRAPH_ID}.json"


def second_graph():
    return {
        "schema_version": 1,
        "id": "ignition-core",
        "title": "Ignition Core Training",
        "description": "A small independent teaching graph.",
        "nodes": [
            {"id": "ignition", "label": "Ignition", "type": "platform", "description": ""}
        ],
        "edges": [],
    }


class GraphStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / SOURCE_GRAPH.name
        self.path.write_bytes(SOURCE_GRAPH.read_bytes())
        self.store = GraphStore(self.directory.name)
        self.graph = self.store.load(GRAPH_ID)

    def test_current_graph_is_valid_and_listed(self):
        self.assertTrue(self.graph["nodes"])
        self.assertTrue(self.graph["edges"])
        self.assertEqual(self.graph["id"], GRAPH_ID)
        self.assertEqual(self.store.list()[0]["title"], "Industrial & Digital Systems")

    def test_repository_contains_six_independent_graphs(self):
        graphs = GraphStore(PROJECT_ROOT / "graphs")
        self.assertEqual(
            {item["id"] for item in graphs.list()},
            {GRAPH_ID, "ignition-core", "isa95-purdue", "security-networking", "autic-products", "application-architecture"},
        )
        self.assertIn("ignition", {node["id"] for node in graphs.load("ignition-core")["nodes"]})

    def test_second_graph_is_independent(self):
        original = self.path.read_bytes()
        self.store.save("ignition-core", second_graph())
        self.assertEqual(
            [item["id"] for item in self.store.list()],
            ["ignition-core", GRAPH_ID],
        )
        self.assertEqual(self.store.load("ignition-core"), second_graph())
        self.assertEqual(self.path.read_bytes(), original)

    def test_rejects_duplicate_ids_and_missing_edge_endpoints(self):
        duplicate = copy.deepcopy(self.graph)
        duplicate["nodes"].append(copy.deepcopy(duplicate["nodes"][0]))
        with self.assertRaisesRegex(GraphValidationError, "duplicate node id"):
            validate_graph(duplicate)

        duplicate_edge = copy.deepcopy(self.graph)
        duplicate_edge["edges"].append(copy.deepcopy(duplicate_edge["edges"][0]))
        with self.assertRaisesRegex(GraphValidationError, "duplicate edge id"):
            validate_graph(duplicate_edge)

        conflicting_id = copy.deepcopy(self.graph)
        conflicting_id["edges"][0]["id"] = conflicting_id["nodes"][0]["id"]
        with self.assertRaisesRegex(GraphValidationError, "conflicts with node id"):
            validate_graph(conflicting_id)

        missing = copy.deepcopy(self.graph)
        missing["edges"].append(
            {"id": "new-edge", "source": "unknown", "target": "enterprise", "relation": "contains"}
        )
        with self.assertRaisesRegex(GraphValidationError, "unknown node"):
            validate_graph(missing)

    def test_rejects_ambiguous_or_invalid_placement_hints(self):
        graph = second_graph()
        graph["placement_hints"] = [
            {"term": "Perspective", "aliases": ["perspective"],
             "parent": "ignition", "relation": "includes", "type": "module",
             "reason": "Course module"},
        ]
        with self.assertRaisesRegex(GraphValidationError, "duplicate placement hint"):
            validate_graph(graph)

        graph["placement_hints"][0]["aliases"] = ["perspective-core"]
        graph["placement_hints"].append({
            "term": "Perspective Core", "parent": "ignition", "relation": "includes",
            "type": "module", "reason": "Course module",
        })
        with self.assertRaisesRegex(GraphValidationError, "duplicate placement hint"):
            validate_graph(graph)

        graph["placement_hints"].pop()
        graph["placement_hints"][0]["aliases"] = []
        graph["placement_hints"][0]["alternates"] = [{"parent": "ignition",
                                                           "relation": "includes"}]
        with self.assertRaisesRegex(GraphValidationError, "duplicate placement parent"):
            validate_graph(graph)

    def test_invalid_graph_does_not_overwrite_file(self):
        original = self.path.read_bytes()
        self.graph["nodes"][0]["id"] = "changed"
        with self.assertRaises(GraphValidationError):
            self.store.save(GRAPH_ID, self.graph)
        self.assertEqual(self.path.read_bytes(), original)

    def test_rejects_path_traversal_and_id_mismatch(self):
        with self.assertRaises(GraphNotFoundError):
            self.store.load("../outside")
        with self.assertRaisesRegex(GraphValidationError, "does not match"):
            self.store.save(GRAPH_ID, second_graph())

    def test_failed_replace_preserves_file_and_removes_temporary_file(self):
        original = self.path.read_bytes()
        self.graph["nodes"][0]["description"] = "Updated description"
        with patch("graph_store.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                save_graph(self.path, self.graph)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])


class GraphRouteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / SOURCE_GRAPH.name
        self.path.write_bytes(SOURCE_GRAPH.read_bytes())
        self.previous_directory = app.config["GRAPH_DATA_DIR"]
        self.previous_testing = app.config["TESTING"]
        app.config.update(GRAPH_DATA_DIR=self.directory.name, TESTING=True)
        self.addCleanup(self.restore_config)
        self.client = app.test_client()

    def restore_config(self):
        app.config.update(
            GRAPH_DATA_DIR=self.previous_directory, TESTING=self.previous_testing
        )

    def test_default_and_scoped_get_use_configured_directory(self):
        default = self.client.get("/api/graph")
        scoped = self.client.get(f"/api/graphs/{GRAPH_ID}")
        self.assertEqual(default.status_code, 200)
        self.assertEqual(default.json, scoped.json)
        self.assertEqual(default.json, load_graph(self.path))

    def test_graph_list_and_missing_graph(self):
        GraphStore(self.directory.name).save("ignition-core", second_graph())
        response = self.client.get("/api/graphs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [graph["id"] for graph in response.json["graphs"]],
            ["ignition-core", GRAPH_ID],
        )
        self.assertEqual(self.client.get("/api/graphs/missing").status_code, 404)

    def test_page_and_local_classification_still_work(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'id="graphSelect"', page.data)
        self.assertIn(b'id="newGraphButton"', page.data)
        self.assertIn(b'id="nodeEditor"', page.data)
        self.assertIn(b'id="edgeEditor"', page.data)
        self.assertIn(b'id="addEdgeButton"', page.data)
        self.assertIn(b'id="themeLegend"', page.data)
        self.assertIn(b'id="resetGraphButton"', page.data)
        self.assertIn(b'data-default-graph-id="industrial-digital-systems"', page.data)
        self.assertIn(b'/static/app.js', page.data)
        script = self.client.get("/static/app.js")
        self.assertEqual(script.status_code, 200)
        script.close()
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            response = self.client.post("/api/classify", json={"term": "MQTT"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["parent"], "data")

    def test_default_add_keeps_unique_ids(self):
        original_source = SOURCE_GRAPH.read_bytes()
        first = self.client.post(
            "/api/add",
            json={"label": "Phase Two Test Concept", "description": "Test", "parent": "data"},
        )
        second = self.client.post(
            "/api/add",
            json={"label": "Phase Two Test Concept", "description": "Another", "parent": "data"},
        )
        edge_collision = self.client.post("/api/add", json={"label": "Edge 0001"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(edge_collision.status_code, 200)
        graph = load_graph(self.path)
        self.assertEqual(first.json["id"], "phase-two-test-concept")
        self.assertEqual(second.json["id"], "phase-two-test-concept-2")
        self.assertEqual(edge_collision.json["id"], "edge-0001-2")
        self.assertTrue(any(node["id"] == second.json["id"] for node in graph["nodes"]))
        self.assertTrue(any(
            edge["source"] == "data"
            and edge["target"] == second.json["id"]
            and edge["relation"] == "contains"
            for edge in graph["edges"]
        ))
        self.assertEqual(SOURCE_GRAPH.read_bytes(), original_source)

    def test_scoped_add_does_not_change_another_graph(self):
        GraphStore(self.directory.name).save("ignition-core", second_graph())
        industrial_before = self.path.read_bytes()
        response = self.client.post(
            "/api/graphs/ignition-core/nodes",
            json={"label": "Gateway", "parent": "ignition"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["id"], "gateway")
        ignition = GraphStore(self.directory.name).load("ignition-core")
        self.assertEqual(len(ignition["nodes"]), 2)
        self.assertEqual(len(ignition["edges"]), 1)
        self.assertEqual(self.path.read_bytes(), industrial_before)

    def test_invalid_parent_and_request_do_not_modify_graph(self):
        original = self.path.read_bytes()
        invalid_parent = self.client.post(
            "/api/add", json={"label": "Test", "parent": "missing"}
        )
        invalid_request = self.client.post("/api/add", json={"label": 123})
        self.assertEqual(invalid_parent.status_code, 400)
        self.assertEqual(invalid_request.status_code, 400)
        self.assertEqual(self.path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
