import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app
from graph_store import GraphStore, load_graph


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class GraphActionRoutesTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.graph_dir = Path(self.directory.name)
        source = PROJECT_ROOT / "graphs" / "industrial-digital-systems.json"
        (self.graph_dir / source.name).write_bytes(source.read_bytes())
        self.store = GraphStore(self.graph_dir)
        self.store.save("ignition-core", {
            "schema_version": 1, "id": "ignition-core", "title": "Ignition Core Training",
            "description": "A small independent teaching graph.",
            "nodes": [{"id": "ignition", "label": "Ignition", "type": "platform",
                       "description": ""}],
            "edges": [],
        })
        self.previous_directory = app.config["GRAPH_DATA_DIR"]
        self.previous_testing = app.config["TESTING"]
        app.config.update(GRAPH_DATA_DIR=str(self.graph_dir), TESTING=True)
        self.addCleanup(self.restore_config)
        self.client = app.test_client()

    def restore_config(self):
        app.config.update(
            GRAPH_DATA_DIR=self.previous_directory, TESTING=self.previous_testing
        )

    def test_create_graph_and_reject_duplicate_or_invalid_id(self):
        industrial_before = (self.graph_dir / "industrial-digital-systems.json").read_bytes()
        created = self.client.post(
            "/api/graphs",
            json={"title": "Autic Learning", "description": "Private practice graph"},
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json["id"], "autic-learning")
        graph = self.store.load("autic-learning")
        self.assertEqual(graph["nodes"], [])
        self.assertEqual(graph["description"], "Private practice graph")
        first_node = self.client.post(
            "/api/graphs/autic-learning/nodes", json={"label": "Customer"}
        )
        self.assertEqual(first_node.status_code, 200)
        self.assertEqual(self.store.load("autic-learning")["nodes"][0]["id"], "customer")
        self.assertEqual(
            self.client.post("/api/graphs", json={"title": "Autic Learning"}).status_code,
            409,
        )
        self.assertEqual(
            self.client.post("/api/graphs", json={"id": "../bad", "title": "Bad"}).status_code,
            400,
        )
        self.assertEqual(
            (self.graph_dir / "industrial-digital-systems.json").read_bytes(),
            industrial_before,
        )

    def test_edit_node_and_delete_its_relationships(self):
        added = self.client.post(
            "/api/graphs/ignition-core/nodes",
            json={"label": "Gateway", "parent": "ignition", "type": "component"},
        )
        self.assertEqual(added.status_code, 200)
        self.assertEqual(added.json["id"], "gateway")
        updated = self.client.patch(
            "/api/graphs/ignition-core/nodes/gateway",
            json={"label": "Gateway Server", "description": "Hosts gateway services", "layer": ""},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json["node"]["id"], "gateway")
        self.assertEqual(updated.json["node"]["label"], "Gateway Server")
        self.assertEqual(
            self.client.patch(
                "/api/graphs/ignition-core/nodes/gateway", json={"id": "renamed"}
            ).status_code,
            400,
        )
        deleted = self.client.delete("/api/graphs/ignition-core/nodes/ignition")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json["removed_edges"], 1)
        graph = self.store.load("ignition-core")
        self.assertEqual([node["id"] for node in graph["nodes"]], ["gateway"])
        self.assertEqual(graph["edges"], [])

    def test_create_edit_and_delete_directed_relationship(self):
        for label in ("Gateway", "Designer"):
            self.assertEqual(
                self.client.post(
                    "/api/graphs/ignition-core/nodes", json={"label": label}
                ).status_code,
                200,
            )
        payload = {
            "source": "designer", "target": "gateway", "relation": "communicates with"
        }
        created = self.client.post("/api/graphs/ignition-core/edges", json=payload)
        self.assertEqual(created.status_code, 201)
        edge_id = created.json["edge"]["id"]
        self.assertEqual(created.json["edge"]["source"], "designer")
        self.assertEqual(
            self.client.post("/api/graphs/ignition-core/edges", json=payload).status_code,
            409,
        )
        updated = self.client.patch(
            f"/api/graphs/ignition-core/edges/{edge_id}",
            json={"source": "gateway", "target": "designer", "relation": "runs on"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json["edge"]["id"], edge_id)
        self.assertEqual(updated.json["edge"]["relation"], "runs on")
        before_invalid = (self.graph_dir / "ignition-core.json").read_bytes()
        invalid = self.client.patch(
            f"/api/graphs/ignition-core/edges/{edge_id}", json={"target": "missing"}
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual((self.graph_dir / "ignition-core.json").read_bytes(), before_invalid)
        self.assertEqual(
            self.client.delete(f"/api/graphs/ignition-core/edges/{edge_id}").status_code,
            200,
        )
        self.assertEqual(self.store.load("ignition-core")["edges"], [])

    def test_missing_items_and_cross_graph_references(self):
        self.assertEqual(
            self.client.patch(
                "/api/graphs/ignition-core/nodes/missing", json={"label": "X"}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete("/api/graphs/ignition-core/edges/missing").status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                "/api/graphs/ignition-core/edges",
                json={"source": "ignition", "target": "enterprise", "relation": "uses"},
            ).status_code,
            400,
        )
        self.assertEqual(self.store.load("ignition-core")["edges"], [])

    def test_reset_ignition_restores_starter_and_backs_up_class_graph(self):
        industrial_before = (self.graph_dir / "industrial-digital-systems.json").read_bytes()
        self.client.post("/api/graphs/ignition-core/nodes", json={
            "label": "Gateway", "parent": "ignition", "layer": "Platform",
        })
        class_graph = self.store.load("ignition-core")
        response = self.client.post("/api/graphs/ignition-core/reset")
        self.assertEqual(response.status_code, 200)
        restored = self.store.load("ignition-core")
        self.assertEqual([node["id"] for node in restored["nodes"]], ["ignition"])
        self.assertEqual(restored["nodes"][0]["layer"], "Platform")
        self.assertEqual(restored["edges"], [])
        self.assertIn("Designer", {hint["term"] for hint in restored["placement_hints"]})
        self.assertIn("Perspective", {hint["term"] for hint in restored["placement_hints"]})
        backup = self.graph_dir / response.json["backup"]
        self.assertEqual(load_graph(backup), class_graph)
        self.assertEqual((self.graph_dir / "industrial-digital-systems.json").read_bytes(),
                         industrial_before)
        self.assertEqual(len(self.store.list()), 2)

        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            gateway = self.client.post("/api/graphs/ignition-core/classify",
                                       json={"term": "Gateway"}).json
        self.assertEqual(gateway["parent"], "ignition")
        self.assertEqual(gateway["layer"], "Platform")
        self.client.post("/api/graphs/ignition-core/nodes", json={
            "label": "Gateway", "parent": gateway["parent"],
            "relation": gateway["relation"], "layer": gateway["layer"],
        })
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            designer = self.client.post("/api/graphs/ignition-core/classify",
                                        json={"term": "Designer"}).json
        self.assertEqual(designer["parent"], "gateway")
        self.assertEqual(designer["relation"], "configured by")
        self.assertEqual(designer["layer"], "Design tools")
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            perspective = self.client.post("/api/graphs/ignition-core/classify",
                                           json={"term": "Perspective"}).json
        self.assertEqual(perspective["parent"], "gateway")
        self.assertEqual(perspective["relation"], "hosts")
        self.assertEqual(perspective["layer"], "Visualization")

    def test_reset_custom_graph_clears_only_its_content(self):
        created = self.client.post("/api/graphs", json={
            "title": "Class Practice", "description": "Reusable classroom graph",
        })
        graph_id = created.json["id"]
        self.client.post(f"/api/graphs/{graph_id}/nodes", json={"label": "Sample"})
        ignition_before = (self.graph_dir / "ignition-core.json").read_bytes()
        response = self.client.post(f"/api/graphs/{graph_id}/reset")
        self.assertEqual(response.status_code, 200)
        restored = self.store.load(graph_id)
        self.assertEqual(restored["title"], "Class Practice")
        self.assertEqual(restored["description"], "Reusable classroom graph")
        self.assertEqual(restored["nodes"], [])
        self.assertEqual(restored["edges"], [])
        self.assertTrue((self.graph_dir / response.json["backup"]).exists())
        self.assertEqual((self.graph_dir / "ignition-core.json").read_bytes(),
                         ignition_before)


if __name__ == "__main__":
    unittest.main()
