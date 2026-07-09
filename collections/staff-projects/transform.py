#!/usr/bin/env python3

import argparse
import json
from collections import defaultdict
from itertools import combinations


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Build staff collaboration graph data from projects/contributors")
    parser.add_argument("--input", default="collections/staff-projects/raw.json", help="Path to GraphQL raw JSON")
    parser.add_argument("--output", default="collections/staff-projects/data.json", help="Path to transformed JSON")
    parser.add_argument("--min-link-weight", type=int, default=1, help="Minimum shared-project count to keep a link")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        raw = json.load(f)

    projects = raw.get("data", {}).get("projects", [])

    staff_names = {}
    staff_projects = defaultdict(set)
    pair_projects = defaultdict(set)
    project_count = 0

    for project in projects:
        project_id = as_int(project.get("post_id"))
        if project_id is None:
            continue

        project_name = (project.get("name") or "").strip() or f"Project {project_id}"
        contributors = project.get("contributors") or []

        contributor_ids = []
        for contributor in contributors:
            staff_id = as_int(contributor.get("post_id"))
            if staff_id is None:
                continue
            staff_name = (contributor.get("name") or "").strip() or f"Staff {staff_id}"
            staff_names[staff_id] = staff_name
            staff_projects[staff_id].add(project_id)
            contributor_ids.append(staff_id)

        unique_ids = sorted(set(contributor_ids))
        if unique_ids:
            project_count += 1
        for a_id, b_id in combinations(unique_ids, 2):
            pair_projects[(a_id, b_id)].add(project_id)

    nodes = []
    for staff_id in sorted(staff_names.keys(), key=lambda x: staff_names[x].lower()):
        projects_for_staff = sorted(staff_projects[staff_id])
        nodes.append(
            {
                "id": str(staff_id),
                "label": staff_names[staff_id],
                "type": "staff",
                "project_count": len(projects_for_staff),
                "projects": projects_for_staff,
            }
        )

    links = []
    for (a_id, b_id), shared_projects in sorted(pair_projects.items(), key=lambda item: (-len(item[1]), item[0])):
        weight = len(shared_projects)
        if weight < args.min_link_weight:
            continue
        links.append(
            {
                "source": str(a_id),
                "target": str(b_id),
                "weight": weight,
                "projects": sorted(shared_projects),
            }
        )

    output = {
        "meta": {
            "source": args.input,
            "transform": "staff-project-collaboration",
            "project_count": project_count,
            "staff_count": len(nodes),
            "link_count": len(links),
            "min_link_weight": args.min_link_weight,
        },
        "data": {
            "nodes": nodes,
            "links": links,
            "projects": [
                {
                    "id": as_int(project.get("post_id")),
                    "name": (project.get("name") or "").strip(),
                }
                for project in projects
                if as_int(project.get("post_id")) is not None
            ],
        },
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote {args.output}")
    print(
        "Built collaboration graph "
        f"({output['meta']['staff_count']} staff, {output['meta']['link_count']} links, {output['meta']['project_count']} projects)"
    )


if __name__ == "__main__":
    main()
