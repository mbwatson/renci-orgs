#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build JS fallback data from org location JSON")
    parser.add_argument("--input", default="orgs.with-locations.json", help="Input JSON file")
    parser.add_argument(
        "--output",
        default="orgs.with-locations.inline.js",
        help="Output JS file that sets window.__ORGS_WITH_LOCATIONS__",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    with input_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    js = (
        "window.__ORGS_WITH_LOCATIONS__ = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )

    with output_path.open("w", encoding="utf-8") as f:
        f.write(js)

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
