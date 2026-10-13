import copy
import tempfile
import unittest
from pathlib import Path

from app import app
from graph_store import GraphStore, GraphValidationError, load_graph, validate_graph


ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "graph_starters" / "isa95-purdue.json"
CURRENT = ROOT / "graphs" / "isa95-purdue.json"


class ISA95GraphTests(unittest.TestCase):
    def test_graph_has_two_connected_views_and_core_models(self):
        graph = load_graph(CURRENT)
        self.assertEqual(graph, load_graph(STARTER))
        self.assertEqual(graph["display_layout"], "hierarchical")
        nodes = {node["id"] for node in graph["nodes"]}
        self.assertTrue({
            "isa95", "isa-l4", "isa-l3", "isa-l2", "isa-l1", "isa-l0",
            "purdue", "purdue-l4", "purdue-l3", "purdue-l2", "purdue-l1",
            "purdue-l0", "industrial-dmz", "equipment-hierarchy", "process-segment",
            "production-ops", "quality-ops", "maintenance-ops", "inventory-ops",
            "operations-definition", "operations-schedule", "operations-performance",
        } <= nodes)

        relationships = {(edge["source"], edge["relation"], edge["target"])
                         for edge in graph["edges"]}
        self.assertIn(("isa-l2", "can be implemented by", "plc-dcs"), relationships)
        self.assertIn(("purdue-l1", "often contains", "plc-dcs"), relationships)
        self.assertIn(("purdue-l4", "may be separated from OT by", "industrial-dmz"),
                      relationships)
        self.assertIn(("industrial-dmz", "can mediate access to", "purdue-l3"),
                      relationships)

        reached = {"model"}
        while True:
            next_reached = reached | {edge["target"] for edge in graph["edges"]
                                      if edge["source"] in reached}
            if next_reached == reached:
                break
            reached = next_reached
        self.assertEqual(reached, nodes)

        indegree = {node_id: 0 for node_id in nodes}
        for edge in graph["edges"]:
            indegree[edge["target"]] += 1
        ready = [node_id for node_id, count in indegree.items() if count == 0]
        self.assertEqual(ready, ["model"])
        visited = 0
        while ready:
            source = ready.pop()
            visited += 1
            for edge in graph["edges"]:
                if edge["source"] == source:
                    indegree[edge["target"]] -= 1
                    if indegree[edge["target"]] == 0:
                        ready.append(edge["target"])
        self.assertEqual(visited, len(nodes))

    def test_reset_restores_new_graph_and_preserves_other_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            graph_path = path / CURRENT.name
            graph_path.write_bytes(CURRENT.read_bytes())
            other_path = path / "industrial-digital-systems.json"
            other_path.write_bytes((ROOT / "graphs" / other_path.name).read_bytes())
            other_before = other_path.read_bytes()
            store = GraphStore(path)
            graph = store.load("isa95-purdue")
            graph["nodes"][0]["description"] = "Class notes"
            store.save("isa95-purdue", graph)
            restored, backup = store.reset("isa95-purdue")
            self.assertEqual(restored, load_graph(STARTER))
            self.assertEqual(load_graph(path / backup)["nodes"][0]["description"],
                             "Class notes")
            self.assertEqual(other_path.read_bytes(), other_before)

    def test_api_lists_and_serves_new_graph(self):
        previous = app.config["GRAPH_DATA_DIR"]
        app.config["GRAPH_DATA_DIR"] = str(ROOT / "graphs")
        try:
            client = app.test_client()
            ids = {entry["id"] for entry in client.get("/api/graphs").json["graphs"]}
            self.assertIn("isa95-purdue", ids)
            response = client.get("/api/graphs/isa95-purdue")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["display_layout"], "hierarchical")
        finally:
            app.config["GRAPH_DATA_DIR"] = previous

    def test_invalid_layout_is_rejected(self):
        graph = copy.deepcopy(load_graph(STARTER))
        graph["display_layout"] = []
        with self.assertRaisesRegex(GraphValidationError, "display_layout"):
            validate_graph(graph)


if __name__ == "__main__":
    unittest.main()
