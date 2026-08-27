"""Loading, indexing and graph extraction for the BSSO Foundry ontologies.

The store is populated in a background thread at start-up (parsing the OWL
sources takes a while), so everything here is written to be safe to read while
a load is still in progress: repositories are published into ``releases`` only
once they are completely parsed.
"""

from dataclasses import dataclass, replace, asdict
import re
import threading
from datetime import date
import traceback
from typing import Literal
from urllib.request import urlopen

import networkx
import networkx.algorithms.dag
import networkx.exception
import pyhornedowl
import requests
from pyhornedowl.model import (
    Class,
    ObjectProperty,
    ObjectPropertyExpression,
    ObjectSomeValuesFrom,
    SubClassOf,
)

RDFSLABEL = "http://www.w3.org/2000/01/rdf-schema#label"

BSSO_CONTENTS_URL = (
    "https://api.github.com/repos/bssofoundry/bssofoundry.github.io"
    "/contents/ontology?ref=main"
)
GITHUB_HEADERS = {"Accept": "application/vnd.github.v3+json"}

DEFN = "http://purl.obolibrary.org/obo/IAO_0000115"
SYN = "http://purl.obolibrary.org/obo/IAO_0000118"

# Sources that the BSSOFoundry metadata does not resolve correctly.
SOURCE_OVERRIDES = {
    "ADDICTO": "https://raw.githubusercontent.com/addiction-ssa/addiction-ontology/master/addicto.owl",
    "BCIO": "https://raw.githubusercontent.com/HumanBehaviourChangeProject/ontologies/master/Upper%20Level%20BCIO/bcio.owl",
    "GMHO": "https://raw.githubusercontent.com/galenos-project/mental-health-ontology/main/gmho.owl",
}

# Graph colours mirror the front-end tokens so a rendered graph sits in the page
# rather than on top of it. Keep in step with frontend/src/styles.css.
REL_COLOURS = {
    "has part": "#1070b8",
    "part of": "#1070b8",
    "contains": "#059669",
    "has role": "#047857",
    "is about": "#6b7280",
    "has participant": "#0b4a7a",
    "_default": "#d97706",
}

PALETTE = {
    "bg": "transparent",
    "node_fill": "#ffffff",
    "node_line": "#94a3b8",
    "node_text": "#0f172a",
    "edge": "#94a3b8",
    "highlight_fill": "#cbe6fb",
    "highlight_line": "#1070b8",
    "highlight_text": "#0b4a7a",
}


def discover_source_repositories() -> dict[str, str]:
    """Read the ontology registry on BSSOFoundry and return ``{id: owl_url}``."""
    response = requests.get(BSSO_CONTENTS_URL, headers=GITHUB_HEADERS, timeout=30)
    response.raise_for_status()

    sources = {}
    for entry in response.json():
        download_url = entry.get("download_url")
        if not download_url or "_outline" in download_url:
            continue

        metadata = requests.get(download_url, headers=GITHUB_HEADERS, timeout=30).text
        repo_name = None
        source_url = None
        for line in metadata.split("\n"):
            if line.startswith("id: ") and "orcid" not in line:
                repo_name = line.replace("id: ", "").strip().upper()
            elif "source_url: " in line:
                source_url = line.replace("source_url: ", "").strip()

        if not repo_name:
            continue
        sources[repo_name] = SOURCE_OVERRIDES.get(repo_name, source_url)

    for repo_name, url in SOURCE_OVERRIDES.items():
        sources[repo_name] = url

    return {name: url for name, url in sources.items() if url}


def wrap_label(label: str, width: int = 18) -> str:
    """Break a label onto several lines so graphviz nodes stay compact."""
    words = label.split()
    if not words:
        return label
    lines, current = [], words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= width:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return "\n".join(lines)


@dataclass(frozen=True)
class Progress:
    state: Literal["idle", "discovering", "loading", "ready", "error"]
    loaded: list[str]
    pending: list[str]
    current: str | None
    failed: dict[str, str]
    error: str | None


@dataclass
class Term:
    id: str
    curie: str
    label: str
    definition: str
    synonyms: list[str]
    iri: str
    repo: str


class OntologyDataStore:
    """Parsed ontologies plus the indexes the API serves from."""

    releases: dict[str, pyhornedowl.PyIndexedOntology]
    loadtimes: dict[str, str]
    graphs: dict[str, networkx.MultiDiGraph]
    terms: dict[str, dict[str, Term]]
    label_to_id: dict[str, dict[str, str]]
    progress: Progress
    sources: dict[str, str]
    _lock: threading.Lock

    def __init__(self, prefixes: dict[str, str], sources: dict[str, str] | None = None):
        self.prefixes = prefixes

        self.releases = {}
        self.loadtimes = {}
        self.graphs = {}
        self.terms = {}  # repo -> {id: term dict}
        self.label_to_id = {}  # repo -> {label: id}

        self.sources = sources if sources is not None else {}
        self.progress = Progress(
            state="idle",
            loaded=[],
            pending=[],
            current=None,
            failed={},
            error=None,
        )
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ load

    def load_all_async(self):
        threading.Thread(
            target=self.load_all, name="ontology-loader", daemon=True
        ).start()

    def load_all(self):
        try:
            if len(self.sources) == 0:
                self._set_progress(state="discovering")
                self.sources =  discover_source_repositories()
            self._set_progress(state="loading", pending=sorted(self.sources))
        except Exception as exc:  # network / GitHub problem
            self._set_progress(
                state="error", error=f"Could not read the ontology registry: {exc}"
            )
            return

        for repo in sorted(self.sources):
            self._set_progress(current=repo)
            try:
                self.parse_release(repo)
                with self._lock:
                    self.progress.loaded.append(repo)
            except Exception as exc:
                print(f"Failed to load {repo}:")
                traceback.print_exc()
                with self._lock:
                    self.progress.failed[repo] = str(exc)
            finally:
                with self._lock:
                    if repo in self.progress.pending:
                        self.progress.pending.remove(repo)

        self._set_progress(state="ready", current=None)

    def _set_progress(self, **kwargs):
        with self._lock:
            self.progress = replace(self.progress, **kwargs)

    def get_progress(self) -> Progress:
        with self._lock:
            return replace(self.progress)

    def parse_release(self, repo: str):
        location = self.sources[repo]
        ontofile = urlopen(location).read().decode("utf-8")
        ontology = pyhornedowl.open_ontology(ontofile)

        for prefix, expansion in self.prefixes.items():
            ontology.prefix_mapping.add_prefix(prefix, expansion) 

        graph = networkx.MultiDiGraph()
        terms = {}
        label_to_id: dict[str, str] = {}

        for class_iri in ontology.get_classes():
            class_id = ontology.get_id_for_iri(class_iri)
            if not class_id:
                continue
            class_id = class_id.replace(":", "_")
            if class_id in terms:
                continue

            label = ontology.get_annotation(class_iri, RDFSLABEL)
            label = label.strip() if label else class_id.replace("_", ":")
            definition = ontology.get_annotation(class_iri, DEFN) or ""
            try:
                synonyms = [
                    s.strip()
                    for s in ontology.get_annotations(class_iri, SYN) or []
                    if s
                ]
            except Exception:
                synonym = ontology.get_annotation(class_iri, SYN)
                synonyms = [synonym.strip()] if synonym else []

            terms[class_id] = Term(
                id=class_id,
                curie=class_id.replace("_", ":"),
                label=label,
                definition=definition.strip(),
                synonyms=synonyms,
                iri=str(class_iri),
                repo=repo,
            )
            label_to_id.setdefault(label, class_id)
            graph.add_node(class_id, label=wrap_label(label), tooltip=label)

        # Subclass edges, drawn from parent to child.
        for class_iri in ontology.get_classes():
            class_id = ontology.get_id_for_iri(class_iri)
            if not class_id:
                continue
            class_id = class_id.replace(":", "_")

            for parent in ontology.get_superclasses(class_iri):
                parent_id = ontology.get_id_for_iri(parent)
                if parent_id and parent_id.replace(":", "_") in terms:
                    graph.add_edge(
                        parent_id.replace(":", "_"), class_id, kind="subclass"
                    )

            for axiom in ontology.get_axioms_for_iri(class_iri):
                component = axiom.component
                match component:
                    case SubClassOf(
                        sup=ObjectSomeValuesFrom(
                            bce=Class(first=_ as target),
                            ope=ObjectProperty(first=_ as ope),
                        )
                    ):

                        rel_name = ontology.get_annotation(str(ope), RDFSLABEL)
                        if not rel_name:
                            continue
                        target_id = ontology.get_id_for_iri(str(target))
                        if not target_id:
                            continue
                        target_id = target_id.replace(":", "_")
                        if target_id not in terms or target_id == class_id:
                            continue

                        graph.add_edge(
                            class_id, target_id, kind="relation", label=rel_name.strip()
                        )

        # Publish only once fully parsed, so readers never see a half-built repo.
        self.releases[repo] = ontology
        self.graphs[repo] = graph
        self.terms[repo] = terms
        self.label_to_id[repo] = label_to_id
        self.loadtimes[repo] = date.today().isoformat()

    # ---------------------------------------------------------------- query

    def available_repos(self) -> list[str]:
        return sorted(self.releases)

    def repo_summaries(self) -> list[dict]:
        return [
            {
                "id": repo,
                "termCount": len(self.terms.get(repo, {})),
                "edgeCount": self.graphs[repo].number_of_edges(),
                "loadedOn": self.loadtimes.get(repo),
                "source": self.sources.get(repo),
            }
            for repo in self.available_repos()
        ]

    def search(self, repos: list[str], query: str, limit: int = 25) -> list[Term]:
        """Rank terms by how well they match ``query`` (id, label or synonym)."""
        query = (query or "").strip().lower()
        if not query:
            return []

        results: list[tuple[int, int, Term]] = []
        for repo in repos:
            for term in self.terms.get(repo, {}).values():
                score = self._score(term, query)
                if score is not None:
                    results.append((score, len(term.label), term))

        results.sort(key=lambda row: (row[0], row[1]))
        return [term for _, _, term in results[:limit]]

    @staticmethod
    def _score(term: Term, query: str) -> int | None:
        """Lower is better; ``None`` means no match."""
        label = term.label.lower()
        curie = term.curie.lower()

        if curie == query or label == query:
            return 0
        if curie.startswith(query):
            return 1
        if label.startswith(query):
            return 2
        if query in label:
            return 3
        if any(query in synonym.lower() for synonym in term.synonyms):
            return 4
        if query in curie:
            return 5
        return None

    def get_term(self, repo: str, term_id: str) -> Term | None:
        return self.terms.get(repo, {}).get(term_id.replace(":", "_"))

    def find_term(self, repos: list[str], term_id: str) -> Term | None:
        for repo in repos:
            term = self.get_term(repo, term_id)
            if term:
                return term
        return None

    def related_ids(self, repo: str, selected_ids: list[str]) -> list[str]:
        """The selected classes plus their ancestors and all their descendants."""
        ontology = self.releases.get(repo)
        graph = self.graphs.get(repo)
        if ontology is None or graph is None:
            raise ValueError(f"Unknown repository '{repo}'")

        ids: set[str] = set()
        for raw_id in selected_ids:
            term_id = raw_id.replace(":", "_")
            if term_id not in self.terms.get(repo, {}):
                continue
            ids.add(term_id)

            entry_iri = ontology.get_iri_for_id(term_id.replace("_", ":"))
            if entry_iri is not None:
                for descendant in ontology.get_descendants(entry_iri):
                    entity_id = ontology.get_id_for_iri(descendant)
                    if entity_id is not None:
                        ids.add(entity_id.replace(":", "_"))
                for superclass in ontology.get_superclasses(entry_iri):
                    entity_id = ontology.get_id_for_iri(superclass)
                    if entity_id is not None:
                        ids.add(entity_id.replace(":", "_"))

            try:
                ids.update(networkx.algorithms.dag.descendants(graph, term_id))
            except networkx.exception.NetworkXError:
                pass

        return sorted(ids)

    def build_subgraph(
        self, repos: list[str], selected_ids: list[str], excluded_ids: list[str]
    ) -> networkx.MultiDiGraph:
        excluded = {i.replace(":", "_") for i in excluded_ids if i}
        subgraphs: list[networkx.MultiDiGraph] = []

        for repo in repos:
            if repo not in self.graphs:
                continue

            match selected_ids:
                case []:
                    ids = set(self.terms.get(repo, {}))
                case _:
                    ids = set(self.related_ids(repo, selected_ids))

            subgraphs.append(self.graphs[repo].subgraph(ids - excluded))

        if len(subgraphs) == 0:
            return networkx.MultiDiGraph()

        return networkx.compose_all(subgraphs)

    # ------------------------------------------------------------------ dot

    def to_dot(
        self, graph: networkx.MultiDiGraph, highlight: set[str] | None = None
    ) -> str:
        """Render a networkx graph as DOT source for graphviz."""
        palette = PALETTE
        colours = REL_COLOURS
        highlight = (
            {i.replace(":", "_") for i in highlight} if highlight is not None else set()
        )

        lines = [
            "digraph ontology {",
            f'  bgcolor="{palette["bg"]}";',
            '  rankdir="TB";',
            "  nodesep=0.35; ranksep=0.6; splines=true; pad=0.4;",
            f'  node [shape=box style="rounded,filled" fontname="Inter,Helvetica,Arial,sans-serif" '
            f'fontsize=11 margin="0.22,0.13" fillcolor="{palette["node_fill"]}" '
            f'color="{palette["node_line"]}" fontcolor="{palette["node_text"]}" penwidth=1.2];',
            f'  edge [color="{palette["edge"]}" fontname="Inter,Helvetica,Arial,sans-serif" '
            f'fontsize=9 fontcolor="{palette["edge"]}" arrowsize=0.7 penwidth=1.1];',
        ]

        for node_id, attrs in graph.nodes(data=True):
            label = attrs.get("label", node_id)
            node_attrs = [
                f'label="{_escape(label)}"',
                f'tooltip="{_escape(attrs.get("tooltip", label))}"',
            ]
            if node_id in highlight:
                node_attrs.append(f'fillcolor="{palette["highlight_fill"]}"')
                node_attrs.append(f'color="{palette["highlight_line"]}"')
                node_attrs.append(f'fontcolor="{palette["highlight_text"]}"')
                node_attrs.append("penwidth=2")
            lines.append(f'  "{node_id}" [{" ".join(node_attrs)}];')

        for source, target, attrs in graph.edges(data=True):
            if attrs.get("kind") == "relation":
                rel_name = attrs.get("label", "")
                colour = colours.get(rel_name, colours["_default"])
                edge_attrs = (
                    f'label="{_escape(rel_name)}" color="{colour}" fontcolor="{colour}"'
                )
            else:
                edge_attrs = f'dir=back color="{palette["edge"]}"'
            lines.append(f'  "{source}" -> "{target}" [{edge_attrs}];')

        lines.append("}")
        return "\n".join(lines)


def _escape(value):
    return re.sub(r'(["\\])', r"\\\1", str(value)).replace("\n", "\\n")
