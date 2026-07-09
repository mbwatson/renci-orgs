#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
REMOTE="${1:-origin}"
BRANCH="${2:-gh-pages}"
VISUALIZATION="${3:-}"
WORKTREE_DIR="/tmp/opencode/renci-orgs-gh-pages-worktree"

if [[ ! -f "$ROOT_DIR/index.html" ]]; then
  printf '%s\n' "Missing $ROOT_DIR/index.html. Run a build first."
  exit 1
fi

if [[ -n "$VISUALIZATION" ]]; then
  if [[ ! -d "$ROOT_DIR/dist/$VISUALIZATION" ]]; then
    printf '%s\n' "Missing $ROOT_DIR/dist/$VISUALIZATION/. Build this visualization first."
    exit 1
  fi
elif [[ ! -d "$ROOT_DIR/dist" ]]; then
  printf '%s\n' "Missing $ROOT_DIR/dist/. Run a build first."
  exit 1
fi

git -C "$ROOT_DIR" worktree remove "$WORKTREE_DIR" --force >/dev/null 2>&1 || true
rm -rf "$WORKTREE_DIR"
git -C "$ROOT_DIR" worktree prune --expire now >/dev/null 2>&1 || true

if git -C "$ROOT_DIR" show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git -C "$ROOT_DIR" worktree add -f "$WORKTREE_DIR" "$BRANCH"
elif git -C "$ROOT_DIR" ls-remote --exit-code --heads "$REMOTE" "$BRANCH" >/dev/null 2>&1; then
  git -C "$ROOT_DIR" fetch "$REMOTE" "$BRANCH:$BRANCH"
  git -C "$ROOT_DIR" worktree add -f "$WORKTREE_DIR" "$BRANCH"
else
  git -C "$ROOT_DIR" worktree add -f --detach "$WORKTREE_DIR"
  git -C "$WORKTREE_DIR" checkout --orphan "$BRANCH"
fi

if [[ -n "$VISUALIZATION" ]]; then
  mkdir -p "$WORKTREE_DIR/dist"
  rm -rf "$WORKTREE_DIR/dist/$VISUALIZATION"
  cp -R "$ROOT_DIR/dist/$VISUALIZATION" "$WORKTREE_DIR/dist/$VISUALIZATION"
  cp "$ROOT_DIR/index.html" "$WORKTREE_DIR/index.html"
else
  git -C "$WORKTREE_DIR" rm -rf . >/dev/null 2>&1 || true
  git -C "$WORKTREE_DIR" clean -fdx >/dev/null 2>&1 || true
  cp "$ROOT_DIR/index.html" "$WORKTREE_DIR/index.html"
  cp -R "$ROOT_DIR/dist" "$WORKTREE_DIR/dist"
fi

touch "$WORKTREE_DIR/.nojekyll"

git -C "$WORKTREE_DIR" add -A

if git -C "$WORKTREE_DIR" diff --cached --quiet; then
  printf '%s\n' "No publish changes detected for $BRANCH."
else
  git -C "$WORKTREE_DIR" commit -m "Publish site artifacts"
  git -C "$WORKTREE_DIR" push "$REMOTE" "$BRANCH"
  printf '%s\n' "Published to $REMOTE/$BRANCH"
fi

git -C "$ROOT_DIR" worktree remove "$WORKTREE_DIR" --force
