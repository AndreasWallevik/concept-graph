
import os, json, re
from flask import Flask, render_template, request, jsonify
from urllib.request import Request, urlopen

app = Flask(__name__)
DATA_PATH = os.path.join(os.path.dirname(__file__), "graph_data.json")

def load_graph():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_graph(data):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/graph")
def get_graph():
    return jsonify(load_graph())

@app.post("/api/add")
def add_node():
    body = request.get_json(force=True)
    graph = load_graph()
    label = body.get("label","").strip()
    description = body.get("description","").strip()
    parent = body.get("parent","").strip()
    node_type = body.get("type","concept").strip() or "concept"
    if not label:
        return jsonify({"error":"label required"}), 400

    base_id = re.sub(r"[^a-z0-9]+","-",label.lower()).strip("-") or "node"
    existing = {n["id"] for n in graph["nodes"]}
    nid = base_id
    i = 2
    while nid in existing:
        nid = f"{base_id}-{i}"
        i += 1

    graph["nodes"].append({
        "id": nid, "label": label, "type": node_type,
        "layer": "Custom", "description": description
    })
    if parent:
        graph["edges"].append({"source": parent, "target": nid, "label":"contains"})
    save_graph(graph)
    return jsonify({"ok":True,"id":nid})

@app.post("/api/classify")
def classify():
    body = request.get_json(force=True)
    term = body.get("term","").strip()
    description = body.get("description","").strip()
    if not term:
        return jsonify({"error":"term required"}), 400

    api_key = os.environ.get("OPENAI_API_KEY")
    graph = load_graph()

    domains = [
        {"id":n["id"],"label":n["label"],"description":n["description"]}
        for n in graph["nodes"] if n["type"] == "domain"
    ]

    if not api_key:
        # deterministic fallback so the app still works without an API key
        text = (term + " " + description).lower()
        rules = [
            ("ai", ["llm","agent","mcp","embedding","vector","rag","prompt"]),
            ("delivery", ["git","ci/cd","pipeline","deploy","docker","kubernetes","ansible","terraform","devops"]),
            ("security", ["security","auth","identity","password","secret","rbac","mfa","zero trust","firewall"]),
            ("data", ["data","mqtt","opc","sql","historian","etl","semantic","namespace","broker","kafka"]),
            ("software", ["api","frontend","backend","middleware","react","service","repository","sdk"]),
            ("mom", ["mes","oee","quality","maintenance","schedule","recipe","batch","trace"]),
            ("supervisory", ["scada","hmi","alarm","supervisory"]),
            ("control", ["plc","dcs","rtu","controller","io","drive"]),
            ("physical", ["sensor","actuator","motor","valve","machine"]),
            ("enterprise", ["erp","crm","warehouse","business","finance","supply chain"]),
            ("cloudedge", ["cloud","edge","on-prem","hybrid"])
        ]
        for parent, words in rules:
            if any(w in text for w in words):
                return jsonify({"parent":parent,"reason":"Local fallback classifier matched keywords. Set OPENAI_API_KEY for AI classification."})
        return jsonify({"parent":"data","reason":"Fallback classifier was uncertain; Data & Integration used as a neutral default."})

    prompt = f"""You classify industrial/software terminology into a knowledge graph.
Choose exactly one parent id from this list:
{json.dumps(domains, ensure_ascii=False)}

Term: {term}
Description: {description}

Return JSON only:
{{"parent":"<id>","reason":"one short sentence","type":"concept|protocol|pattern|component|tool|platform|framework|risk"}}
"""

    req = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps({
            "model":"gpt-5-mini",
            "input": prompt
        }).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":"application/json"
        },
        method="POST"
    )
    try:
        with urlopen(req, timeout=30) as r:
            payload = json.loads(r.read().decode("utf-8"))
        output_text = payload.get("output_text","")
        match = re.search(r"\{.*\}", output_text, re.S)
        if not match:
            return jsonify({"error":"AI returned no parsable JSON","raw":output_text}), 500
        return jsonify(json.loads(match.group(0)))
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=True)
