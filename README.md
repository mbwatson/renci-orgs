# renci-org-viz

Static, embeddable RENCI visualizations with a reproducible fetch -> transform -> build pipeline.

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

- `just list`: list configured collections and visualizations.
- `just fetch <collection>`: fetch raw source data.
- `just transform <collection>`: create prepared data artifact.
- `just refresh <collection>`: fetch + transform for one collection.
- `just build <visualization>`: build one visualization.
- `just build`: build all visualizations.
- `just run <visualization>`: transform + build one visualization.
- `just run-refresh <visualization>`: fetch + transform + build one visualization.
- `just serve`: start a local static server on port 8000.
- `just serve 8001`: start server on a different port if 8000 is already in use.
- `just dev`: run `run-refresh partners-map` then serve on port 8000.
- `just dev <visualization> <port>`: run `run-refresh` for one visualization and serve locally.
- `just publish <visualization>`: build and publish one visualization to `origin/gh-pages`.
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

## Add a New Visualization

### 1) Create a collection

Create a folder: `collections/<collection-name>/`

Add `collections/<collection-name>/collection.yaml`:

```yaml
name: <collection-name>

source:
  type: graphql
  endpoint: https://website-content.apps.renci.org/graphql
  endpoint_override_env: VIZGEN_GRAPHQL_ENDPOINT
  query: collections/<collection-name>/query.graphql
  output: collections/<collection-name>/raw.json

transform:
  file: collections/<collection-name>/transform.py
  output: collections/<collection-name>/data.json
```

Add `collections/<collection-name>/query.graphql` (example):

```graphql
query ExampleCollection {
  projects(page: { offset: 0, limit: 50 }) {
    post_id
    name
  }
}
```

Add `collections/<collection-name>/transform.py`:

```python
#!/usr/bin/env python3

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="collections/<collection-name>/raw.json")
    parser.add_argument("--output", default="collections/<collection-name>/data.json")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        raw = json.load(f)

    output = {
        "meta": {"source": args.input},
        "data": raw.get("data", {}),
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
```

Run collection steps:

- `just fetch <collection-name>`
- `just transform <collection-name>`

### 2) Create a visualization

Create a folder: `visualizations/<visualization-name>/`

Add `visualizations/<visualization-name>/visualization.yaml`:

```yaml
name: <visualization-name>

data:
  collection: <collection-name>

build:
  entry: visualizations/<visualization-name>/index.html
  output: dist/<visualization-name>
```

Add `visualizations/<visualization-name>/index.html`:

- Build client-side only.
- Read prepared data from `./data.json`.
- Optional fallback: `window.__VIZGEN_INLINE_DATA__`.

Build and test:

- `just build <visualization-name>`
- `just serve 8000`
- Open `http://localhost:8000/` and click your visualization from the generated index page.

### 3) Publish

- Single visualization: `just publish <visualization-name>`
- All visualizations: `just publish-all`

For WordPress iframe embeds, use:

- `https://mbwatson.github.io/renci-org-viz/dist/<visualization-name>/index.html`

## Publishing (VPN-Friendly)

Because GraphQL is VPN-restricted, builds run locally and publish prebuilt static files.

- `just build` or `just build-all` on VPN.
- `just publish <visualization>` to push one built page and refreshed root index.
- `just publish-all` to push all built pages and root index.
- GitHub Pages then serves the static artifacts without needing GraphQL access.

## Embedding

- Preferred iframe target: `https://mbwatson.github.io/renci-org-viz/dist/<visualization>/index.html`
- In WordPress shortcode plugins, keep attributes minimal first and add extras after verifying render.
- If an embed suddenly shows something unexpected, like a 404 page, clear WordPress/CDN cache and retest in a private browser window.
