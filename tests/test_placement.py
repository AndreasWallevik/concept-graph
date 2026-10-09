import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app
from classifier import local_suggestion
from graph_store import GraphStore, load_graph


IGNITION_STARTER = Path(__file__).resolve().parents[1] / "graph_starters" / "ignition-core.json"


class PlacementTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.store = GraphStore(self.path)
        self.store.save("training", {
            "schema_version": 1, "id": "training", "title": "Training",
            "description": "A small training graph",
            "nodes": [
                {"id": "gateway", "label": "Gateway", "type": "platform",
                 "description": "Hosts gateway services"},
                {"id": "server", "label": "Server", "type": "component",
                 "description": "Runs applications"},
            ],
            "edges": [
                {"id": "edge-1", "source": "gateway", "target": "server",
                 "relation": "runs on"},
            ],
        })
        self.store.save("empty", {
            "schema_version": 1, "id": "empty", "title": "Empty",
            "description": "", "nodes": [], "edges": [],
        })
        self.previous_directory = app.config["GRAPH_DATA_DIR"]
        self.previous_testing = app.config["TESTING"]
        app.config.update(GRAPH_DATA_DIR=self.directory.name, TESTING=True)
        self.addCleanup(lambda: app.config.update(
            GRAPH_DATA_DIR=self.previous_directory, TESTING=self.previous_testing))
        self.client = app.test_client()

    def test_local_suggestion_uses_selected_graph_and_does_not_save(self):
        before = (self.path / "training.json").read_bytes()
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            result = self.client.post("/api/graphs/training/classify",
                                      json={"term": "Gateway service"})
            empty = self.client.post("/api/graphs/empty/classify",
                                     json={"term": "Gateway service"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["parent"], "gateway")
        self.assertEqual(result.json["relation"], "runs on")
        self.assertEqual(result.json["source"], "local")
        self.assertIsNone(empty.json["parent"])
        self.assertIsNone(empty.json["relation"])
        self.assertEqual((self.path / "training.json").read_bytes(), before)

    def test_suggestion_relation_can_be_accepted_when_adding(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            suggestion = self.client.post("/api/graphs/training/classify",
                                          json={"term": "Gateway service"}).json
        added = self.client.post("/api/graphs/training/nodes", json={
            "label": "Gateway service", "parent": suggestion["parent"],
            "relation": suggestion["relation"],
        })
        self.assertEqual(added.status_code, 200)
        self.assertTrue(any(
            edge["source"] == "gateway" and edge["target"] == added.json["id"]
            and edge["relation"] == "runs on"
            for edge in self.store.load("training")["edges"]
        ))

    def test_duplicate_and_uncertain_terms_do_not_invent_a_connection(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            duplicate = self.client.post("/api/graphs/training/classify",
                                         json={"term": "Server"})
            uncertain = self.client.post("/api/graphs/training/classify",
                                         json={"term": "Unrelated widget"})
        self.assertEqual(duplicate.json["existing_node"], "server")
        self.assertEqual(duplicate.json["parent"], "gateway")
        self.assertEqual(duplicate.json["relation"], "runs on")
        self.assertIsNone(uncertain.json["parent"])
        self.assertIsNone(uncertain.json["relation"])

    def test_invalid_relation_does_not_add_a_concept(self):
        before = (self.path / "training.json").read_bytes()
        result = self.client.post("/api/graphs/training/nodes", json={
            "label": "New service", "parent": "gateway", "relation": "",
        })
        self.assertEqual(result.status_code, 400)
        self.assertEqual((self.path / "training.json").read_bytes(), before)

    def test_graph_hint_connects_designer_to_gateway_regardless_of_case(self):
        graph = self.store.load("training")
        graph["nodes"][0]["layer"] = "Platform"
        graph["placement_hints"] = [{
            "term": "Designer", "parent": "gateway", "relation": "configured by",
            "type": "tool", "layer": "Design tools",
            "reason": "Designer connects to the Gateway.",
        }]
        self.store.save("training", graph)
        before = (self.path / "training.json").read_bytes()
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            for term in ("Designer", "designer", "DESIGNER"):
                result = self.client.post("/api/graphs/training/classify",
                                          json={"term": term})
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json["parent"], "gateway")
                self.assertEqual(result.json["relation"], "configured by")
                self.assertEqual(result.json["layer"], "Design tools")
                self.assertEqual(result.json["source"], "hint")
        self.assertEqual((self.path / "training.json").read_bytes(), before)

        graph["nodes"].append({"id": "designer", "label": "Designer", "type": "tool"})
        self.store.save("training", graph)
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            existing = self.client.post("/api/graphs/training/classify",
                                        json={"term": "designer"})
        self.assertEqual(existing.json["existing_node"], "designer")
        self.assertEqual(existing.json["parent"], "gateway")
        self.assertFalse(existing.json["relationship_exists"])

    def test_course_hint_uses_available_parent_and_later_suggests_specific_edge(self):
        graph = load_graph(IGNITION_STARTER)
        broad = local_suggestion(graph, "Flex Container", "")
        self.assertEqual((broad["parent"], broad["relation"]), ("ignition", "includes"))
        self.assertEqual(broad["layer"], "Perspective")

        graph["nodes"].append({"id": "perspective", "label": "Perspective", "type": "module"})
        module_level = local_suggestion(graph, "Flex Container", "")
        self.assertEqual((module_level["parent"], module_level["relation"]),
                         ("perspective", "uses"))

        graph["nodes"].append({"id": "view", "label": "View", "type": "screen"})
        graph["nodes"].append({"id": "flex-container", "label": "Flex Container",
                               "type": "container", "layer": "Perspective"})
        graph["edges"].append({"id": "broad-edge", "source": "ignition",
                               "target": "flex-container", "relation": "includes"})
        specific = local_suggestion(graph, "flex container", "")
        self.assertEqual(specific["existing_node"], "flex-container")
        self.assertEqual((specific["parent"], specific["relation"]), ("view", "contains"))
        self.assertFalse(specific["relationship_exists"])

    def test_course_hints_cover_chapters_and_aliases(self):
        graph = load_graph(IGNITION_STARTER)
        for term, expected_layer in [
            ("Gateway", "Platform"), ("Tag UDT", "Devices and tags"),
            ("Perspective", "Visualization"), ("Alarming", "Alarming"),
            ("Tag History", "History and data"), ("Transaction Group", "History and data"),
            ("Report", "Reporting"), ("Vision", "Visualization"),
            ("Gateway Backup", "Backups"),
        ]:
            with self.subTest(term=term):
                result = local_suggestion(graph, term, "")
                self.assertEqual(result["source"], "hint")
                self.assertEqual(result["layer"], expected_layer)
                self.assertIn(result["parent"], {node["id"] for node in graph["nodes"]})

        graph["nodes"].append({"id": "gateway", "label": "Gateway", "type": "service"})
        self.assertEqual(local_suggestion(graph, "Perspective", "")["parent"], "gateway")
        self.assertEqual(local_suggestion(graph, "designer", "")["relation"], "configured by")

    def test_historian_terms_resolve_to_83_concepts_and_existing_alias(self):
        graph = load_graph(IGNITION_STARTER)
        graph["nodes"].extend([
            {"id": "gateway", "label": "Gateway", "type": "service"},
            {"id": "tag-historian", "label": "Tag Historian", "type": "module"},
        ])
        graph["edges"].append({"id": "history-module", "source": "gateway",
                               "target": "tag-historian", "relation": "hosts"})

        existing = local_suggestion(graph, "Historian", "")
        self.assertEqual(existing["existing_node"], "tag-historian")
        self.assertEqual((existing["parent"], existing["relation"]), ("gateway", "hosts"))
        self.assertTrue(existing["relationship_exists"])
        self.assertEqual(local_suggestion(graph, "tag_historian", "")["existing_node"],
                         "tag-historian")

        history = local_suggestion(graph, "History", "")
        self.assertEqual((history["parent"], history["relation"]), ("gateway", "manages"))
        self.assertEqual(history["source"], "hint")
        self.assertEqual(local_suggestion(graph, "Core Historian", "")["parent"],
                         "tag-historian")
        self.assertEqual(local_suggestion(graph, "Tag History", "")["parent"],
                         "tag-historian")
        sql = local_suggestion(graph, "SQL Historian", "")
        self.assertEqual((sql["parent"], sql["relation"], sql["type"]),
                         ("tag-historian", "supports", "history provider"))

        graph["nodes"].append({"id": "sql-historian-module", "label": "SQL Historian Module",
                               "type": "module"})
        sql_with_module = local_suggestion(graph, "SQL Historian", "")
        self.assertEqual((sql_with_module["parent"], sql_with_module["relation"]),
                         ("sql-historian-module", "provides"))

    def test_saved_perspective_can_accept_suggested_connection(self):
        graph = self.store.load("training")
        graph["placement_hints"] = [{
            "term": "Perspective", "parent": "gateway", "relation": "hosts",
            "type": "module", "layer": "Visualization",
            "reason": "Perspective is installed in the Gateway.",
        }]
        graph["nodes"].append({
            "id": "perspective", "label": "Perspective", "type": "concept",
        })
        graph["edges"].append({
            "id": "edge-2", "source": "server", "target": "perspective",
            "relation": "contains",
        })
        self.store.save("training", graph)
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            suggestion = self.client.post("/api/graphs/training/classify",
                                          json={"term": "Perspective"}).json
        self.assertEqual(suggestion["existing_node"], "perspective")
        self.assertEqual(suggestion["parent"], "gateway")
        self.assertEqual(suggestion["relation"], "hosts")
        self.assertFalse(suggestion["relationship_exists"])
        linked = self.client.post("/api/graphs/training/edges", json={
            "source": suggestion["parent"], "target": suggestion["existing_node"],
            "relation": suggestion["relation"],
        })
        self.assertEqual(linked.status_code, 201)
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            again = self.client.post("/api/graphs/training/classify",
                                     json={"term": "Perspective"}).json
        self.assertTrue(again["relationship_exists"])

    def test_ai_request_uses_selected_graph_and_raw_response_output(self):
        model_result = {"parent": "gateway", "relation": "runs on",
                        "type": "component", "reason": "Gateway hosts the service."}
        response = {"output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(model_result)}]}]}
        before = (self.path / "training.json").read_bytes()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}), \
                patch("classifier.urlopen", return_value=io.BytesIO(
                    json.dumps(response).encode("utf-8"))) as send:
            result = self.client.post("/api/graphs/training/classify",
                                      json={"term": "Gateway service"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["source"], "ai")
        self.assertEqual(result.json["relation"], "runs on")
        request_body = json.loads(send.call_args.args[0].data)
        self.assertFalse(request_body["store"])
        self.assertEqual(request_body["text"]["format"]["type"], "json_schema")
        context = json.loads(request_body["input"].split("\n\n", 1)[1])
        self.assertEqual(context["graph"]["title"], "Training")
        self.assertEqual(context["edges"][0]["relation"], "runs on")
        self.assertEqual((self.path / "training.json").read_bytes(), before)

    def test_invalid_ai_reference_falls_back_to_this_graph(self):
        response = {"output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps({
                "parent": "industrial-data", "relation": "runs on",
                "type": "component", "reason": "Wrong graph",
            })}]}]}
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}), \
                patch("classifier.urlopen", return_value=io.BytesIO(
                    json.dumps(response).encode("utf-8"))):
            result = self.client.post("/api/graphs/training/classify",
                                      json={"term": "Gateway service"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["source"], "local")
        self.assertEqual(result.json["parent"], "gateway")
        self.assertIn("AI suggestion unavailable", result.json["reason"])


if __name__ == "__main__":
    unittest.main()
