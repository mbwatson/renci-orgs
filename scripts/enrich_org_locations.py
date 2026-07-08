#!/usr/bin/env python3

import argparse
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional


USER_AGENT = "renci-org-location-enricher/1.0 (local script)"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"


STOP_WORDS = {
    "the",
    "of",
    "and",
    "for",
    "in",
    "at",
    "on",
    "inc",
    "llc",
    "ltd",
    "university",
    "institute",
    "center",
    "centre",
    "department",
    "school",
    "hospital",
    "office",
    "national",
}


def normalize_text(value: str) -> str:
    text = html.unescape(value or "").lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokens(value: str) -> List[str]:
    raw = normalize_text(value).split()
    return [t for t in raw if t and t not in STOP_WORDS]


def fetch_json(url: str, timeout: int = 20, retries: int = 4) -> Dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            last_error = err
            if err.code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except urllib.error.URLError as err:
            last_error = err
            time.sleep(1.5 * (attempt + 1))
    if last_error:
        raise last_error
    raise RuntimeError("fetch_json failed unexpectedly")


def search_nominatim(query: str, limit: int = 5) -> List[Dict]:
    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": "1",
        "limit": str(limit),
    }
    url = f"{NOMINATIM_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    data = fetch_json(url)
    if isinstance(data, list):
        return data
    return []


def score_candidate(org_name: str, candidate: Dict) -> int:
    org_tokens = set(tokens(org_name))
    cand_text = " ".join(
        [
            candidate.get("name", ""),
            candidate.get("display_name", ""),
            candidate.get("type", ""),
            candidate.get("class", ""),
        ]
    )
    cand_tokens = set(tokens(cand_text))

    overlap = 0.0
    if org_tokens:
        overlap = len(org_tokens & cand_tokens) / len(org_tokens)

    importance = float(candidate.get("importance", 0.0) or 0.0)
    score = int(overlap * 80 + importance * 20)

    class_name = candidate.get("class", "")
    if class_name in {"amenity", "office", "building", "education", "healthcare"}:
        score += 5

    return score


@dataclass
class Resolution:
    status: str
    latitude: Optional[float]
    longitude: Optional[float]
    place: Optional[str]
    provider_id: Optional[str]
    score: int
    source_query: str


def resolve_org(org: Dict, min_score: int) -> Resolution:
    name = html.unescape(org.get("name", "")).strip()
    try:
        candidates = search_nominatim(name)
    except Exception:
        return Resolution(
            status="lookup_error",
            latitude=None,
            longitude=None,
            place=None,
            provider_id=None,
            score=0,
            source_query=name,
        )

    if not candidates:
        return Resolution(
            status="unresolved",
            latitude=None,
            longitude=None,
            place=None,
            provider_id=None,
            score=0,
            source_query=name,
        )

    best = None
    best_score = -1
    for cand in candidates:
        score = score_candidate(name, cand)
        if score > best_score:
            best = cand
            best_score = score

    if not best:
        return Resolution(
            status="unresolved",
            latitude=None,
            longitude=None,
            place=None,
            provider_id=None,
            score=0,
            source_query=name,
        )

    lat = best.get("lat")
    lon = best.get("lon")
    try:
        lat_f = float(lat) if lat is not None else None
        lon_f = float(lon) if lon is not None else None
    except ValueError:
        lat_f = None
        lon_f = None

    status = "resolved" if best_score >= min_score and lat_f is not None and lon_f is not None else "low_confidence"
    return Resolution(
        status=status,
        latitude=lat_f,
        longitude=lon_f,
        place=best.get("display_name"),
        provider_id=str(best.get("osm_id")) if best.get("osm_id") is not None else None,
        score=best_score,
        source_query=name,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich org list with map coordinates via OpenStreetMap Nominatim")
    parser.add_argument("--input", default="orgs.json", help="Path to source org JSON")
    parser.add_argument("--output", default="orgs.with-locations.json", help="Path for enriched output")
    parser.add_argument("--min-score", type=int, default=20, help="Minimum confidence score for accepted match")
    parser.add_argument("--sleep", type=float, default=1.1, help="Delay between requests in seconds")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        src = json.load(f)

    orgs = src.get("data", {}).get("organizations", [])
    enriched_orgs = []
    status_count: Dict[str, int] = {}

    for org in orgs:
        result = resolve_org(org, args.min_score)
        status_count[result.status] = status_count.get(result.status, 0) + 1

        org_out = dict(org)
        org_out["location"] = {
            "status": result.status,
            "provider": "nominatim",
            "provider_id": result.provider_id,
            "latitude": result.latitude,
            "longitude": result.longitude,
            "place": result.place,
            "score": result.score,
            "source_query": result.source_query,
        }
        enriched_orgs.append(org_out)
        time.sleep(args.sleep)

    output = {
        "meta": {
            "source": args.input,
            "resolver": "nominatim",
            "min_score": args.min_score,
            "counts": status_count,
        },
        "data": {
            "organizations": enriched_orgs,
        },
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    total = len(orgs)
    resolved = status_count.get("resolved", 0)
    print(f"Wrote {args.output}")
    print(f"Resolved {resolved}/{total} organizations")
    print("Status counts:")
    for status in sorted(status_count.keys()):
        print(f"  {status}: {status_count[status]}")


if __name__ == "__main__":
    main()
