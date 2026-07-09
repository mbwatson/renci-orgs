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
from pathlib import Path
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


def resolution_to_dict(result: Resolution) -> Dict:
    return {
        "status": result.status,
        "latitude": result.latitude,
        "longitude": result.longitude,
        "place": result.place,
        "provider_id": result.provider_id,
        "score": result.score,
        "source_query": result.source_query,
    }


def resolution_from_dict(value: Dict, min_score: int) -> Optional[Resolution]:
    if not isinstance(value, dict):
        return None

    source_query = str(value.get("source_query") or "")
    score = int(value.get("score") or 0)
    latitude = value.get("latitude")
    longitude = value.get("longitude")

    lat_ok = isinstance(latitude, (int, float))
    lon_ok = isinstance(longitude, (int, float))

    raw_status = str(value.get("status") or "")
    if raw_status in {"unresolved", "lookup_error"}:
        status = raw_status
    else:
        status = "resolved" if score >= min_score and lat_ok and lon_ok else "low_confidence"

    return Resolution(
        status=status,
        latitude=float(latitude) if lat_ok else None,
        longitude=float(longitude) if lon_ok else None,
        place=value.get("place"),
        provider_id=value.get("provider_id"),
        score=score,
        source_query=source_query,
    )


def load_cache(path: Path) -> Dict[str, Dict]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(payload, dict):
        return {}
    entries = payload.get("entries", payload)
    if not isinstance(entries, dict):
        return {}
    return {str(k): v for k, v in entries.items() if isinstance(v, dict)}


def save_cache(path: Path, entries: Dict[str, Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": {
            "provider": "nominatim",
            "entry_count": len(entries),
            "updated_at_unix": int(time.time()),
        },
        "entries": entries,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


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
    parser.add_argument("--progress-every", type=int, default=25, help="Print progress every N organizations")
    parser.add_argument("--cache", default="cache/geocodes.json", help="Path to geocode cache JSON")
    parser.add_argument("--no-cache", action="store_true", help="Disable cache reads/writes for this run")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        src = json.load(f)

    orgs = src.get("data", {}).get("organizations", [])
    total = len(orgs)
    enriched_orgs = []
    status_count: Dict[str, int] = {}

    cache_path = Path(args.cache)
    cache_entries: Dict[str, Dict] = {} if args.no_cache else load_cache(cache_path)
    cache_hits = 0
    looked_up = 0
    cache_writes = 0

    estimated_seconds = int(total * max(args.sleep, 0.0))
    print(
        f"Starting geocode transform for {total} organizations (minimum delay budget ~{estimated_seconds}s)",
        flush=True,
    )
    if args.no_cache:
        print("Cache disabled for this run", flush=True)
    else:
        print(f"Using geocode cache: {cache_path} ({len(cache_entries)} entries)", flush=True)

    for index, org in enumerate(orgs, start=1):
        org_name = html.unescape(org.get("name", "")).strip()
        cache_key = normalize_text(org_name)

        result = None
        if cache_key and not args.no_cache:
            result = resolution_from_dict(cache_entries.get(cache_key), args.min_score)
            if result is not None:
                cache_hits += 1

        requested_lookup = False
        if result is None:
            result = resolve_org(org, args.min_score)
            requested_lookup = True
            looked_up += 1

            if cache_key and not args.no_cache and result.status != "lookup_error":
                cache_entries[cache_key] = resolution_to_dict(result)
                cache_writes += 1

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

        if args.progress_every > 0 and (index % args.progress_every == 0 or index == total):
            resolved = status_count.get("resolved", 0)
            print(
                f"Progress {index}/{total} (resolved: {resolved}, cache hits: {cache_hits}, lookups: {looked_up})",
                flush=True,
            )

        if requested_lookup and index < total:
            time.sleep(args.sleep)

    if not args.no_cache:
        save_cache(cache_path, cache_entries)

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

    resolved = status_count.get("resolved", 0)
    print(f"Wrote {args.output}", flush=True)
    print(f"Resolved {resolved}/{total} organizations", flush=True)
    print(f"Cache hits: {cache_hits}, live lookups: {looked_up}, cache writes: {cache_writes}", flush=True)
    print("Status counts:", flush=True)
    for status in sorted(status_count.keys()):
        print(f"  {status}: {status_count[status]}", flush=True)


if __name__ == "__main__":
    main()
