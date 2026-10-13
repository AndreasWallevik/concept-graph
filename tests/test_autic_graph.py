"""Checks that the public-source Autic demo stays connected and discoverable."""

import copy
import unittest
from pathlib import Path
from urllib.parse import urlparse

from app import app
from graph_store import GraphValidationError, load_graph, validate_graph


ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "graphs" / "autic-products.json"
STARTER = ROOT / "graph_starters" / "autic-products.json"


class AuticGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = load_graph(GRAPH)

    def test_source_backed_demo_is_connected(self):
        nodes = {node["id"]: node for node in self.graph["nodes"]}
        self.assertGreaterEqual(len(nodes), 20)
        self.assertLessEqual(len(nodes), 50)
        self.assertGreater(len(self.graph["edges"]), len(nodes))
        self.assertEqual(self.graph["color_by"], "type")
        self.assertTrue(self.graph["discovery_mode"])
        self.assertEqual(self.graph, load_graph(STARTER))

        adjacency = {node_id: set() for node_id in nodes}
        for edge in self.graph["edges"]:
            adjacency[edge["source"]].add(edge["target"])
            adjacency[edge["target"]].add(edge["source"])
        reached = {"product-ignition"}
        frontier = list(reached)
        while frontier:
            for neighbor in adjacency[frontier.pop()]:
                if neighbor not in reached:
                    reached.add(neighbor)
                    frontier.append(neighbor)
        self.assertEqual(reached, set(nodes))

        for node in nodes.values():
            self.assertTrue(node["description"])
            parsed = urlparse(node["url"])
            self.assertEqual(parsed.scheme, "https")
            self.assertEqual(parsed.hostname, "www.autic.no")

    def test_exploratory_paths(self):
        edges = {(edge["source"], edge["relation"], edge["target"])
                 for edge in self.graph["edges"]}
        for path in (
            ("product-ignition", "SUPPORTS_PROTOCOL", "protocol-opcua"),
            ("product-da10d", "SUPPORTS_PROTOCOL", "protocol-opcua"),
            ("product-ignition", "USED_FOR", "application-scada"),
            ("product-xedge", "USED_FOR", "application-scada"),
            ("product-ignition-edge", "PART_OF_FAMILY", "product-ignition"),
            ("product-groov-rio", "INTEGRATES_WITH", "product-ignition-edge"),
            ("product-nt4008", "MANUFACTURED_BY", "brand-red-lion"),
        ):
            self.assertIn(path, edges)

    def test_optional_discovery_fields_are_validated(self):
        invalid = copy.deepcopy(self.graph)
        invalid["nodes"][0]["url"] = "javascript:alert(1)"
        with self.assertRaisesRegex(GraphValidationError, "HTTPS URL"):
            validate_graph(invalid)
        invalid = copy.deepcopy(self.graph)
        invalid["discovery_mode"] = "yes"
        with self.assertRaisesRegex(GraphValidationError, "boolean"):
            validate_graph(invalid)

    def test_graph_and_controls_are_served(self):
        with app.test_client() as client:
            graph = client.get("/api/graphs/autic-products")
            page = client.get("/?graph=autic-products")
        self.assertEqual(graph.status_code, 200)
        self.assertEqual(graph.json["id"], "autic-products")
        self.assertIn(b'id="typeFilter"', page.data)
        self.assertIn(b'id="resetViewButton"', page.data)


if __name__ == "__main__":
    unittest.main()
