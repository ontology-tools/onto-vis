# onto-vis

Web app for exploring and visualising the [BSSO Foundry](https://bssofoundry.github.io/)
behavioural science ontologies (BCIO, AddictO, GMHO and others).

A Flask JSON API loads and indexes the OWL sources; a Vue 3 single-page app
searches them and lays the graph out in the browser with graphviz compiled to
WebAssembly, so panning, zooming and selecting are all client-side.

## Layout

| Path                | What it is                                                    |
| ------------------- | ------------------------------------------------------------- |
| `app.py`            | Flask app — creates the store, mounts the API, serves the SPA |
| `api.py`            | JSON API blueprint under `/api`                                |
| `ontology_store.py` | Downloads, parses and indexes the ontologies; builds the DOT   |
| `config.py`         | Prefix map and Flask settings                                  |
| `frontend/`         | Vue 3 + Vite single-page app                                   |
| `static/`           | Logo artwork, served at `/static`                              |

## Running it

Install the Python dependencies and build the front end once:

```bash
pip install -r requirements.txt          # or: uv sync
cd frontend && npm install && npm run build && cd ..
```

Then start the server, which serves both the API and the built app:

```bash
python app.py                            # http://127.0.0.1:5001
```

The ontologies are downloaded and parsed in a background thread at start-up and
take a minute or two. The app shows a progress screen and polls `/api/status`
until the store reports `ready`.

### Front-end development

Run the Vue dev server alongside Flask for hot reloading. It proxies `/api` and
`/static` to port 5001:

```bash
python app.py                            # terminal 1
cd frontend && npm run dev               # terminal 2 — http://127.0.0.1:5173
```

`frontend/dist` is git-ignored, so build it on deploy (or drop that line from
`.gitignore` if you would rather commit it).

If `npm run dev` fails with `EMFILE`, the machine has run out of inotify
instances (`/proc/sys/fs/inotify/max_user_instances`, often exhausted by editors).
Either raise it, or start the dev server with `CHOKIDAR_USEPOLLING=1 npm run dev`.

## API

| Endpoint            | Purpose                                                        |
| ------------------- | -------------------------------------------------------------- |
| `GET /api/status`   | Load progress and the list of available ontologies              |
| `GET /api/ontologies` | Loaded ontologies with class and relation counts              |
| `GET /api/terms`    | Type-ahead search — `?repo=BCIO&q=behaviour&limit=25`           |
| `GET /api/terms/<id>` | One class, by CURIE (`BCIO:050578`) or id (`BCIO_050578`)     |
| `POST /api/graph`   | DOT for a selection — `{repos, include, exclude}`                |

A graph is drawn from the selected classes together with their ancestors and all
of their descendants. With no selection, the whole ontology is drawn.

## Sharing a view

The selection lives in the query string, so a rendered graph survives a reload and
can be linked to:

```
/?repo=BCIO,ADDICTO&include=BCIO:003000,ADDICTO:0000769&exclude=BCIO:028000
```

Each parameter is a comma-separated list; `include`/`exclude` accept either CURIEs
(`BCIO:003000`) or underscore ids (`BCIO_003000`). Ids that no longer resolve are
dropped and the rest of the graph still renders. The URL is rewritten whenever a
graph is rendered.
