set shell := ["bash", "-cu"]

default:
  @just --list

check:
  test -f vizgen.py
  test -f vizgen.config.yaml
  test -f index.html
  test -f scripts/build_embedded_fallback.py
  test -d collections
  test -d visualizations

list:
  python3 vizgen.py list

fetch collection: check
  python3 vizgen.py fetch {{collection}}

transform collection: check
  python3 vizgen.py transform {{collection}}

refresh collection: check
  python3 vizgen.py fetch {{collection}}
  python3 vizgen.py transform {{collection}}

build visualization='': check
  @if [ -n "{{visualization}}" ]; then \
    python3 vizgen.py build "{{visualization}}"; \
  else \
    python3 vizgen.py build; \
  fi

run visualization: check
  python3 vizgen.py run {{visualization}}

run-refresh visualization: check
  python3 vizgen.py run {{visualization}} --refresh

build-all: check
  python3 vizgen.py build

serve port='8000':
  python3 -m http.server {{port}}

dev visualization='partners-map' port='8000': check
  python3 vizgen.py run {{visualization}} --refresh
  just serve {{port}}

publish visualization remote='origin' branch='gh-pages': check
  python3 vizgen.py build {{visualization}}
  bash scripts/publish_gh_pages.sh {{remote}} {{branch}} {{visualization}}

publish-all remote='origin' branch='gh-pages': build-all
  bash scripts/publish_gh_pages.sh {{remote}} {{branch}}

clean:
  mkdir -p dist
  rm -f collections/*/data.json
  rm -rf dist/*
