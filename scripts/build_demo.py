"""Build the static Autic discovery demo from the current app and graph."""

import sys
from pathlib import Path
from shutil import copyfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from graph_store import load_graph


OUTPUT = ROOT / "demo"
GRAPH = ROOT / "graphs" / "autic-products.json"
TEMPLATE = ROOT / "templates" / "index.html"
SCRIPT = ROOT / "static" / "app.js"


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Expected one occurrence of {old!r} in template")
    return text.replace(old, new)


def main():
    graph = load_graph(GRAPH)
    if graph["id"] != "autic-products" or not graph.get("discovery_mode"):
        raise ValueError("The Autic demo requires the Autic discovery graph")

    html = TEMPLATE.read_text(encoding="utf-8")
    html = replace_once(
        html,
        'data-default-graph-id="{{ default_graph_id }}"',
        'data-default-graph-id="autic-products" data-demo-mode="true"',
    )
    html = replace_once(
        html,
        "{{ url_for('static', filename='app.js') }}",
        "./app.js",
    )
    if "{{" in html or "{%" in html:
        raise ValueError("Unresolved template expression in demo HTML")

    OUTPUT.mkdir(exist_ok=True)
    unexpected = {path.name for path in OUTPUT.iterdir()} - {
        "index.html", "app.js", "graph.json"
    }
    if unexpected:
        raise ValueError(f"Unexpected files in public demo directory: {sorted(unexpected)}")
    (OUTPUT / "index.html").write_text(html, encoding="utf-8")
    copyfile(SCRIPT, OUTPUT / "app.js")
    copyfile(GRAPH, OUTPUT / "graph.json")
    print(f"Built {OUTPUT} from {GRAPH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
