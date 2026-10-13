import tempfile
import unittest
from collections import Counter, defaultdict, deque
from pathlib import Path

from app import app
from graph_store import load_graph


ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "graph_starters" / "security-networking.json"
CURRENT = ROOT / "graphs" / "security-networking.json"


class SecurityNetworkingGraphTests(unittest.TestCase):
    def test_seed_is_connected_by_domains_and_has_meaningful_paths(self):
        graph = load_graph(CURRENT)
        self.assertEqual(graph, load_graph(STARTER))
        self.assertEqual(graph["id"], "security-networking")
        self.assertEqual(len(graph["nodes"]), 132)
        self.assertEqual(len(graph["edges"]), 289)

        nodes = {node["id"]: node for node in graph["nodes"]}
        domains = {node["label"]: node["id"] for node in graph["nodes"]
                   if node["type"] == "domain"}
        self.assertEqual(len(domains), 13)
        self.assertEqual(len({node["label"].casefold() for node in nodes.values()}),
                         len(nodes))
        self.assertTrue(all(node["description"].strip() for node in nodes.values()))
        self.assertNotIn("hashkey", {node_id.casefold() for node_id in nodes})
        for term in ("SSH", "IdP", "JWT", "DHCP", "ARP", "VLAN", "NAT",
                     "TLS", "HMAC", "RBAC", "DMZ", "Zero Trust", "NIS2",
                     "UUID", "GUID"):
            self.assertTrue(any(term.casefold() in node["label"].casefold()
                                for node in nodes.values()), term)

        coverage = Counter(edge["target"] for edge in graph["edges"]
                           if edge["relation"] == "covers")
        edges = {(edge["source"], edge["relation"], edge["target"])
                 for edge in graph["edges"]}
        for node in nodes.values():
            if node["type"] == "domain":
                self.assertEqual(coverage[node["id"]], 0)
            else:
                self.assertEqual(coverage[node["id"]], 1)
                self.assertIn((domains[node["layer"]], "covers", node["id"]),
                              edges)

        self.assertEqual(len(edges), len(graph["edges"]))
        for relationship in [
            ("dhcp", "leases", "ip-address"),
            ("https", "uses", "tls"),
            ("oidc", "extends", "oauth"),
            ("jwt", "can format", "access-token"),
            ("hmac", "requires", "secret"),
            ("digital-signature", "verified with", "public-key"),
            ("vlan", "segments Layer 2 traffic on", "lan"),
            ("iec62443", "defines security requirements for", "ics"),
            ("ip-address", "understand before", "subnet"),
            ("networking", "understand before", "protocols"),
        ]:
            self.assertIn(relationship, edges)

        prerequisites = [(edge["source"], edge["target"])
                         for edge in graph["edges"]
                         if edge["relation"] == "understand before"]
        self.assertGreaterEqual(len(prerequisites), 25)
        indegree = Counter(target for _, target in prerequisites)
        next_nodes = defaultdict(list)
        for source, target in prerequisites:
            next_nodes[source].append(target)
        ready = deque(node_id for node_id in nodes if indegree[node_id] == 0)
        visited = 0
        while ready:
            source = ready.popleft()
            visited += 1
            for target in next_nodes[source]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
        self.assertEqual(visited, len(nodes), "learning prerequisites must not cycle")

    def test_api_lists_and_serves_new_graph(self):
        previous = app.config["GRAPH_DATA_DIR"]
        app.config["GRAPH_DATA_DIR"] = str(ROOT / "graphs")
        try:
            client = app.test_client()
            ids = {item["id"] for item in client.get("/api/graphs").json["graphs"]}
            self.assertIn("security-networking", ids)
            response = client.get("/api/graphs/security-networking")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["title"], "Security & Networking")
            self.assertTrue(next(node["description"] for node in response.json["nodes"]
                                 if node["id"] == "jwt"))
        finally:
            app.config["GRAPH_DATA_DIR"] = previous

    def test_custom_concept_and_reset_leave_other_graph_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            (temp / CURRENT.name).write_bytes(CURRENT.read_bytes())
            other = temp / "ignition-core.json"
            other.write_bytes((ROOT / "graphs" / other.name).read_bytes())
            other_before = other.read_bytes()
            previous = app.config["GRAPH_DATA_DIR"]
            app.config["GRAPH_DATA_DIR"] = str(temp)
            try:
                client = app.test_client()
                added = client.post("/api/graphs/security-networking/nodes", json={
                    "label": "Custom Network Control",
                    "description": "A learner's additional network security control.",
                    "type": "concept",
                    "layer": "Network Security",
                    "parent": "network-security-domain",
                    "relation": "covers",
                })
                self.assertEqual(added.status_code, 200)
                changed = client.get("/api/graphs/security-networking").json
                self.assertIn(added.json["id"],
                              {node["id"] for node in changed["nodes"]})
                reset = client.post("/api/graphs/security-networking/reset")
                self.assertEqual(reset.status_code, 200)
                self.assertEqual(load_graph(temp / CURRENT.name), load_graph(STARTER))
                self.assertEqual(other.read_bytes(), other_before)
                backup = load_graph(temp / reset.json["backup"])
                self.assertIn(added.json["id"],
                              {node["id"] for node in backup["nodes"]})
            finally:
                app.config["GRAPH_DATA_DIR"] = previous


if __name__ == "__main__":
    unittest.main()
