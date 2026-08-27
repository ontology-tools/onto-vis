"""JSON API consumed by the Vue front end."""

from flask import Blueprint, current_app, jsonify, request

api = Blueprint("api", __name__, url_prefix="/api")

MAX_FULL_GRAPH_NODES = 4000


def store():
    return current_app.extensions["ontology_store"]


def _requested_repos(default_to_all=True):
    """Read ``repo``/``repos`` from the query string or JSON body."""
    payload = request.get_json(silent=True) or {}
    raw = payload.get("repos") or request.args.getlist("repo") or request.args.get("repos")

    if isinstance(raw, str):
        raw = [part for part in raw.split(",") if part]
    repos = [repo.upper() for repo in (raw or [])]

    available = store().available_repos()
    repos = [repo for repo in repos if repo in available]
    if not repos and default_to_all:
        repos = available
    return repos


@api.get("/status")
def status():
    """Loading progress — the front end polls this until ``ready``."""
    progress = store().get_progress()
    progress["repositories"] = store().repo_summaries()
    return jsonify(progress)


@api.get("/ontologies")
def ontologies():
    return jsonify(store().repo_summaries())


@api.get("/terms")
def terms():
    """Type-ahead search across the selected ontologies."""
    query = request.args.get("q", "")
    limit = min(int(request.args.get("limit", 25)), 100)
    results = store().search(_requested_repos(), query, limit=limit)
    return jsonify(results)


@api.get("/terms/<term_id>")
def term_detail(term_id):
    term = store().find_term(_requested_repos(), term_id)
    if term is None:
        return jsonify({"error": f"Unknown term '{term_id}'"}), 404
    return jsonify(term)


@api.post("/graph")
def graph():
    """Build a DOT document for the requested selection."""
    payload = request.get_json(silent=True) or {}
    repos = _requested_repos(default_to_all=False)
    if not repos:
        return jsonify({"error": "Choose at least one ontology."}), 400

    include = _clean_ids(payload.get("include"))
    exclude = _clean_ids(payload.get("exclude"))

    subgraph = store().build_subgraph(repos, include, exclude)
    node_count = subgraph.number_of_nodes()

    if node_count == 0:
        return jsonify({
            "error": "That selection produced an empty graph — try different or fewer exclusions.",
            "nodeCount": 0,
            "edgeCount": 0,
        }), 200

    if not include and node_count > MAX_FULL_GRAPH_NODES:
        return jsonify({
            "error": (
                f"The full graph has {node_count:,} classes, which is too large to lay out in the "
                "browser. Add one or more terms to narrow it down."
            ),
            "nodeCount": node_count,
            "edgeCount": subgraph.number_of_edges(),
        }), 200

    dot = store().to_dot(subgraph, highlight=include)
    return jsonify({
        "dot": dot,
        "nodeCount": node_count,
        "edgeCount": subgraph.number_of_edges(),
        "repos": repos,
    })


def _clean_ids(values):
    """Accept ids, CURIEs, or the legacy ``ID|label`` form."""
    if isinstance(values, str):
        values = values.split(",")
    cleaned = []
    for value in values or []:
        if isinstance(value, dict):
            value = value.get("id") or value.get("curie") or ""
        value = str(value).split("|")[0].strip()
        if value:
            cleaned.append(value)
    return cleaned
