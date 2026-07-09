#!/usr/bin/env python3

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected mapping in {path}")
    return data


def load_config() -> dict:
    cfg_path = ROOT / "vizgen.config.yaml"
    if not cfg_path.exists():
        return {}
    return load_yaml(cfg_path)


def root_join(path_str: str) -> Path:
    return (ROOT / path_str).resolve()


def default_raw_path(collection_name: str, collection_cfg: dict) -> Path:
    source_cfg = collection_cfg.get("source", {})
    raw_path = source_cfg.get("output") or source_cfg.get("path")
    if raw_path:
        return root_join(raw_path)
    return root_join(f"collections/{collection_name}/raw.json")


def data_output_path(collection_name: str, collection_cfg: dict) -> Path:
    transform_cfg = collection_cfg.get("transform", {})
    output = transform_cfg.get("output")
    if output:
        return root_join(output)
    return root_join(f"collections/{collection_name}/data.json")


def transform_path(collection_cfg: dict) -> Path:
    transform_cfg = collection_cfg.get("transform", {})
    transform_file = transform_cfg.get("file")
    if not transform_file:
        raise RuntimeError("Collection config is missing transform.file")
    path = root_join(transform_file)
    if not path.exists():
        raise RuntimeError(f"Transform file not found: {transform_file}")
    return path


def collection_config_path(name: str, app_cfg: dict) -> Path:
    collections_dir = app_cfg.get("paths", {}).get("collections_dir", "collections")
    return root_join(f"{collections_dir}/{name}/collection.yaml")


def load_collection_config(name: str, app_cfg: dict) -> dict:
    cfg_path = collection_config_path(name, app_cfg)
    if not cfg_path.exists():
        raise RuntimeError(f"Collection config not found: {cfg_path.relative_to(ROOT)}")
    return load_yaml(cfg_path)


def visualization_config_paths(app_cfg: dict) -> list[Path]:
    visualizations_dir = app_cfg.get("paths", {}).get("visualizations_dir", "visualizations")
    return sorted((ROOT / visualizations_dir).glob("*/visualization.yaml"))


def visualization_config_path(name: str, app_cfg: dict) -> Path:
    visualizations_dir = app_cfg.get("paths", {}).get("visualizations_dir", "visualizations")
    return root_join(f"{visualizations_dir}/{name}/visualization.yaml")


def load_visualization_config(name: str, app_cfg: dict) -> dict:
    cfg_path = visualization_config_path(name, app_cfg)
    if not cfg_path.exists():
        raise RuntimeError(f"Visualization config not found: {cfg_path.relative_to(ROOT)}")
    return load_yaml(cfg_path)


def collection_names(app_cfg: dict) -> list[str]:
    collections_dir = ROOT / app_cfg.get("paths", {}).get("collections_dir", "collections")
    return sorted(path.parent.name for path in collections_dir.glob("*/collection.yaml"))


def visualization_names(app_cfg: dict) -> list[str]:
    return sorted(path.parent.name for path in visualization_config_paths(app_cfg))


def generate_root_index(app_cfg: dict) -> Path:
    rows = []
    for cfg_path in visualization_config_paths(app_cfg):
        viz_name = cfg_path.parent.name
        cfg = load_yaml(cfg_path)
        display_name = cfg.get("name") or viz_name
        collection_name = cfg.get("data", {}).get("collection", "unknown")
        output_path = cfg.get("build", {}).get("output") or f"dist/{viz_name}"
        output_dir = root_join(output_path)
        route = f"./{output_path.strip('/')}/"
        built = (output_dir / "index.html").exists()
        status = "Ready" if built else "Not built"
        status_class = "ready" if built else "missing"
        rows.append(
            "".join(
                [
                    "<li class=\"viz-card\">",
                    f"<h2>{html.escape(display_name)}</h2>",
                    f"<p class=\"meta\">id: <code>{html.escape(viz_name)}</code></p>",
                    f"<p class=\"meta\">collection: <code>{html.escape(collection_name)}</code></p>",
                    f"<p class=\"status {status_class}\">{status}</p>",
                    f"<a href=\"{html.escape(route)}\">Open visualization</a>",
                    "</li>",
                ]
            )
        )

    body = "\n      ".join(rows) if rows else "<li class=\"viz-card\"><p>No visualizations configured.</p></li>"
    page = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>vizgen Visualizations</title>
  <style>
    :root {{
      --bg-a: #edf5fb;
      --bg-b: #dfeef8;
      --ink: #12324a;
      --muted: #486278;
      --line: rgba(21, 58, 85, 0.16);
      --card: rgba(255, 255, 255, 0.86);
      --link: #0f6ba8;
      --ready: #0a7d4e;
      --missing: #98610a;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; }}
    body {{
      min-height: 100vh;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      color: var(--ink);
      background: linear-gradient(145deg, var(--bg-a), var(--bg-b));
      padding: 22px;
    }}
    .shell {{ max-width: 960px; margin: 0 auto; }}
    h1 {{ margin: 0 0 8px; font-size: 1.5rem; }}
    .intro {{ margin: 0 0 18px; color: var(--muted); }}
    .viz-list {{
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    }}
    .viz-card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      box-shadow: 0 6px 16px rgba(17, 53, 77, 0.08);
    }}
    .viz-card h2 {{ margin: 0 0 8px; font-size: 1rem; }}
    .meta {{ margin: 0 0 6px; color: var(--muted); font-size: 0.85rem; }}
    .status {{ margin: 0 0 9px; font-size: 0.82rem; font-weight: 600; }}
    .status.ready {{ color: var(--ready); }}
    .status.missing {{ color: var(--missing); }}
    a {{ color: var(--link); text-decoration: none; font-weight: 600; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <main class=\"shell\">
    <h1>Visualization Index</h1>
    <p class=\"intro\">Routes are generated from visualization configs. Build status reflects whether each `dist/<name>/index.html` exists.</p>
    <ul class=\"viz-list\">
      {body}
    </ul>
  </main>
</body>
</html>
"""
    out = ROOT / "index.html"
    out.write_text(page, encoding="utf-8")
    print(f"Generated root index -> {out.relative_to(ROOT)}")
    return out


def expand_env_placeholders(value):
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, dict):
        return {k: expand_env_placeholders(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_env_placeholders(v) for v in value]
    return value


def fetch_graphql(collection_name: str, collection_cfg: dict, app_cfg: dict) -> Path:
    source_cfg = collection_cfg.get("source", {})
    endpoint = source_cfg.get("endpoint")
    endpoint_env = source_cfg.get("endpoint_override_env") or source_cfg.get("endpoint_env")
    if endpoint_env:
        endpoint = os.environ.get(endpoint_env, endpoint)

    if not endpoint:
        raise RuntimeError(
            f"Collection '{collection_name}' needs source.endpoint or source.endpoint_override_env to fetch GraphQL data"
        )

    query_path = source_cfg.get("query")
    if not query_path:
        raise RuntimeError(f"Collection '{collection_name}' is missing source.query")

    query_file = root_join(query_path)
    if not query_file.exists():
        raise RuntimeError(f"Query file not found: {query_path}")

    query_text = query_file.read_text(encoding="utf-8")
    variables = expand_env_placeholders(source_cfg.get("variables", {}))
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "vizgen/0.1",
    }
    headers.update(expand_env_placeholders(source_cfg.get("headers", {})))

    timeout_s = app_cfg.get("defaults", {}).get("graphql_timeout_seconds", 30)
    payload = json.dumps({"query": query_text, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GraphQL request failed: HTTP {err.code} {body[:400]}") from err
    except urllib.error.URLError as err:
        raise RuntimeError(f"GraphQL request failed: {err.reason}") from err

    try:
        response_payload = json.loads(body)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"GraphQL endpoint returned invalid JSON: {err}") from err

    errors = response_payload.get("errors")
    if errors:
        first_msg = errors[0].get("message") if isinstance(errors, list) and errors else str(errors)
        raise RuntimeError(f"GraphQL returned errors: {first_msg}")

    raw_path = default_raw_path(collection_name, collection_cfg)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with raw_path.open("w", encoding="utf-8") as f:
        json.dump(response_payload, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Fetched GraphQL data -> {raw_path.relative_to(ROOT)}")
    return raw_path


def run_transform(collection_name: str, collection_cfg: dict, raw_path: Path) -> Path:
    transform_file = transform_path(collection_cfg)
    output_path = data_output_path(collection_name, collection_cfg)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(transform_file),
        "--input",
        str(raw_path),
        "--output",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)
    return output_path


def fetch_collection(name: str, app_cfg: dict) -> Path:
    collection_cfg = load_collection_config(name, app_cfg)
    source_type = collection_cfg.get("source", {}).get("type")

    if source_type == "graphql":
        raw_path = fetch_graphql(name, collection_cfg, app_cfg)
    elif source_type == "file":
        raw_path = default_raw_path(name, collection_cfg)
        if not raw_path.exists():
            raise RuntimeError(f"Source file for collection '{name}' not found: {raw_path.relative_to(ROOT)}")
        print(f"Source file ready -> {raw_path.relative_to(ROOT)}")
    else:
        raise RuntimeError(f"Unsupported source type for collection '{name}': {source_type}")

    return raw_path


def transform_collection(name: str, app_cfg: dict) -> Path:
    collection_cfg = load_collection_config(name, app_cfg)
    raw_path = default_raw_path(name, collection_cfg)
    if not raw_path.exists():
        raise RuntimeError(
            f"Raw data not found for collection '{name}': {raw_path.relative_to(ROOT)}. Run `vizgen fetch {name}` first."
        )

    data_path = run_transform(name, collection_cfg, raw_path)
    print(f"Transformed collection -> {data_path.relative_to(ROOT)}")
    return data_path


def build_visualization(name: str, app_cfg: dict) -> Path:
    viz_cfg = load_visualization_config(name, app_cfg)
    collection_name = viz_cfg.get("data", {}).get("collection")
    if not collection_name:
        raise RuntimeError(f"Visualization '{name}' missing data.collection")

    collection_cfg_path = collection_config_path(collection_name, app_cfg)
    collection_cfg = load_yaml(collection_cfg_path)
    data_path = data_output_path(collection_name, collection_cfg)
    if not data_path.exists():
        raise RuntimeError(
            f"Collection data not found for '{collection_name}': {data_path.relative_to(ROOT)}. Run `vizgen transform {collection_name}` first."
        )

    build_cfg = viz_cfg.get("build", {})
    entry_str = build_cfg.get("entry")
    output_str = build_cfg.get("output")
    if not entry_str or not output_str:
        raise RuntimeError(f"Visualization '{name}' missing build.entry or build.output")

    entry_path = root_join(entry_str)
    output_dir = root_join(output_str)
    source_dir = entry_path.parent

    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(source_dir, output_dir, ignore=shutil.ignore_patterns("visualization.yaml", "data.inline.js"))

    fallback_builder = ROOT / "scripts" / "build_embedded_fallback.py"
    inline_output = output_dir / "data.inline.js"
    subprocess.run(
        [
            sys.executable,
            str(fallback_builder),
            "--input",
            str(data_path),
            "--output",
            str(inline_output),
        ],
        check=True,
    )

    shutil.copy2(data_path, output_dir / "data.json")

    print(f"Built visualization '{name}' -> {output_dir.relative_to(ROOT)}")
    return output_dir


def run_visualization(name: str, app_cfg: dict, refresh: bool) -> Path:
    viz_cfg = load_visualization_config(name, app_cfg)
    collection_name = viz_cfg.get("data", {}).get("collection")
    if not collection_name:
        raise RuntimeError(f"Visualization '{name}' missing data.collection")

    if refresh:
        fetch_collection(collection_name, app_cfg)
    transform_collection(collection_name, app_cfg)
    return build_visualization(name, app_cfg)


def list_entities(kind: str, app_cfg: dict) -> None:
    if kind in {"collections", "all"}:
        print("collections")
        for name in collection_names(app_cfg):
            print(f"- {name}")

    if kind in {"visualizations", "all"}:
        print("visualizations")
        for name in visualization_names(app_cfg):
            print(f"- {name}")


def cmd_init(app_cfg: dict) -> None:
    paths_cfg = app_cfg.get("paths", {})
    collections_dir = ROOT / paths_cfg.get("collections_dir", "collections")
    visualizations_dir = ROOT / paths_cfg.get("visualizations_dir", "visualizations")
    dist_dir = ROOT / paths_cfg.get("dist_dir", "dist")
    cache_dir = ROOT / paths_cfg.get("cache_dir", "cache")

    for path in (collections_dir, visualizations_dir, dist_dir, cache_dir):
        path.mkdir(parents=True, exist_ok=True)
        print(f"Ensured {path.relative_to(ROOT)}/")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="vizgen: static visualization build tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialize vizgen project folders")

    fetch_parser = subparsers.add_parser("fetch", help="Fetch raw collection data")
    fetch_parser.add_argument("collection", help="Collection name (folder under collections/)")

    transform_parser = subparsers.add_parser("transform", help="Transform fetched raw collection data")
    transform_parser.add_argument("collection", help="Collection name (folder under collections/)")

    build_parser = subparsers.add_parser("build", help="Build one visualization or all")
    build_parser.add_argument("visualization", nargs="?", help="Visualization name (folder under visualizations/)")

    run_parser = subparsers.add_parser("run", help="Transform collection and build a visualization")
    run_parser.add_argument("visualization", help="Visualization name (folder under visualizations/)")
    run_parser.add_argument("--refresh", action="store_true", help="Fetch source data before transform")

    list_parser = subparsers.add_parser("list", help="List available collections and visualizations")
    list_parser.add_argument(
        "kind",
        nargs="?",
        default="all",
        choices=["all", "collections", "visualizations"],
        help="What to list",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app_cfg = load_config()

    if args.command == "init":
        cmd_init(app_cfg)
        return
    if args.command == "fetch":
        fetch_collection(args.collection, app_cfg)
        return
    if args.command == "transform":
        transform_collection(args.collection, app_cfg)
        return
    if args.command == "build":
        if args.visualization:
            build_visualization(args.visualization, app_cfg)
            generate_root_index(app_cfg)
            return
        viz_paths = visualization_config_paths(app_cfg)
        for viz_path in viz_paths:
            viz_name = viz_path.parent.name
            build_visualization(viz_name, app_cfg)
        generate_root_index(app_cfg)
        return
    if args.command == "run":
        run_visualization(args.visualization, app_cfg, refresh=args.refresh)
        return
    if args.command == "list":
        list_entities(args.kind, app_cfg)
        return

    raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)
