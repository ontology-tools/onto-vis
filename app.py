"""onto-vis — Flask API and host for the Vue front end.

The OWL sources take a while to download and parse, so the store is filled on a
background thread while the app already answers requests. ``/api/status`` reports
progress and the front end shows a loading screen until it reads ``ready``.

"""

from pathlib import Path

from flask import Flask, send_from_directory
from flask_cors import CORS

from api import api
from ontology_store import OntologyDataStore

BASE_DIR = Path(__file__).parent
DIST_DIR = BASE_DIR / "frontend" / "dist"


def create_app():
    app = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="/static")
    app.config.from_object("config")

    # The Vue dev server runs on another origin; the API is public data anyway.
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    store = OntologyDataStore(app.config["PREFIXES"], app.config.get("SOURCES"))
    app.extensions["ontology_store"] = store
        
    store.load_all_async()

    app.register_blueprint(api)

    register_spa_routes(app)
    return app


def register_spa_routes(app):
    """Serve the built front end, falling back to index.html for client routes."""


    @app.get("/assets/logo")
    def dynamic_logo():
        return send_from_directory(BASE_DIR / "static", "bcio-vis.jpg" if "BCIO" in app.config.get("SOURCES", {}) else "onto-vis.jpg")

    @app.get("/assets/<path:filename>")
    def spa_assets(filename):
        return send_from_directory(DIST_DIR / "assets", filename)

    @app.get("/")
    @app.get("/<path:path>")
    def spa(path=""):
        # A real file in dist (favicon, etc.) wins; anything else is a Vue route.
        candidate = (DIST_DIR / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(DIST_DIR.resolve()):
            return send_from_directory(DIST_DIR, path)

        return send_from_directory(DIST_DIR, "index.html")


app = create_app()


if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"], port=5001, use_reloader=False)
