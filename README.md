# renci-orgs

Static partner organization map with a reproducible local data-prep pipeline.

## Prerequisites

- Python 3
- `just`

## GraphQL Source

- Default endpoint is set in `collections/partners/collection.yaml`: `https://website-content.apps.renci.org/graphql`
- To override locally, set: `export VIZGEN_GRAPHQL_ENDPOINT="https://example.org/graphql"`
- Optional auth header via env expansion in `collections/partners/collection.yaml` if needed.

## vizgen CLI

- `python3 vizgen.py init`: ensure `collections/`, `visualizations/`, `dist/`, and `cache/` exist.
- `python3 vizgen.py list`: show available collections and visualizations.
- `python3 vizgen.py fetch <collection>`: execute source fetch and write `collections/<collection>/raw.json`.
- `python3 vizgen.py transform <collection>`: run transform and write `collections/<collection>/data.json`.
- `python3 vizgen.py build <visualization>`: build a single visualization into `dist/<visualization>/`.
- `python3 vizgen.py build`: build all visualizations.
- `python3 vizgen.py run <visualization>`: transform that visualization's collection, then build it.
- `python3 vizgen.py run <visualization> --refresh`: fetch + transform + build in one command.

## Workflow

- `just list`: wrapper for `python3 vizgen.py list`.
- `just fetch partners`: wrapper for `python3 vizgen.py fetch partners`.
- `just transform partners`: wrapper for `python3 vizgen.py transform partners`.
- `just refresh partners`: wrapper for fetch + transform for one collection.
- `just build partners-map`: build one visualization.
- `just build`: build all visualizations.
- `just run partners-map`: transform + build one visualization.
- `just run-refresh partners-map`: fetch + transform + build one visualization.
- `just serve`: start a local static server on port 8000.
- `just serve 8001`: start server on a different port if 8000 is already in use.
- `just dev`: run `run-refresh partners-map` then serve on port 8000.
- `just dev partners-map 8001`: run `run-refresh` for a visualization, then serve on a chosen port.
- `just publish staff-projects-graph`: build and publish one visualization to `origin/gh-pages`.
- `just publish-all`: build and publish all visualizations to `origin/gh-pages`.
- `just publish-all upstream gh-pages`: publish all visualizations to a specific remote/branch.
- `just clean`: remove generated artifacts.

Note: `transform` for partners uses `cache/geocodes.json` by default to avoid repeated live lookups; first run can still take several minutes.
Note: `build` expects `collections/<name>/data.json` to exist; if missing, run `transform` (or `run`) first.

Open `http://localhost:<port>` after running `just serve` or `just dev`.
The root page is an auto-generated index of all configured visualizations and links to `dist/<visualization>/` routes.
Run a build first (`just build`, `just run ...`, or `just dev`) so routes are ready.

## Artifacts

- `collections/partners/raw.json`: source organization dataset.
- `collections/partners/data.json`: enriched organization dataset with location metadata.
- `collections/staff-projects/raw.json`: source project/contributor dataset.
- `collections/staff-projects/data.json`: transformed staff collaboration graph data.
- `dist/<visualization>/data.inline.js`: embedded fallback payload generated during build.
- `dist/<visualization>/`: staged static output for deployment.

## Scripts

- `collections/partners/transform.py`: resolves organization locations via Nominatim and writes enriched JSON.
- `scripts/build_embedded_fallback.py`: converts enriched JSON into a JS fallback assignment.

## Pipeline

- Collection: `collections/partners/query.graphql` -> GraphQL endpoint -> `collections/partners/raw.json` -> `collections/partners/transform.py` -> `collections/partners/data.json`
- Visualization: `visualizations/partners-map/index.html` + `collections/partners/data.json` -> `dist/partners-map/`
- Collection: `collections/staff-projects/query.graphql` -> GraphQL endpoint -> `collections/staff-projects/raw.json` -> `collections/staff-projects/transform.py` -> `collections/staff-projects/data.json`
- Visualization: `visualizations/staff-projects-graph/index.html` + `collections/staff-projects/data.json` -> `dist/staff-projects-graph/`

## Example Multi-Module Commands

- `python3 vizgen.py fetch partners`
- `python3 vizgen.py transform partners`
- `python3 vizgen.py build partners-map`
- `python3 vizgen.py run staff-projects-graph --refresh`

## Publishing (VPN-Friendly)

Because GraphQL is VPN-restricted, builds run locally and publish prebuilt static files.

- `just build` or `just build-all` on VPN.
- `just publish <visualization>` to push one built page and refreshed root index.
- `just publish-all` to push all built pages and root index.
- GitHub Pages then serves the static artifacts without needing GraphQL access.
