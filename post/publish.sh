#!/bin/sh
# Rebuild docs/, commit everything and push; GitHub Pages republishes the site about a minute later.
#   post/publish.sh "Commit message"
# If BLOCKLIST names a file of private terms (one per line), the push is refused when a changed file contains one.
set -e
cd "$(dirname "$0")/.."
uv run --quiet --with markdown post/build.py
git add -A
if [ -n "$BLOCKLIST" ]; then
  terms=$(mktemp); grep -v '^[[:space:]]*$' "$BLOCKLIST" > "$terms"
  hits=$(git diff --cached --name-only | while read -r f; do
    # the project's own addresses (repository and Pages site) are allowed
    if [ -f "$f" ] && tr '[:upper:]' '[:lower:]' < "$f" | sed -e 's#runfme/claude-computer-use-trace##g' -e 's#runfme.github.io/claude-computer-use-trace##g' | grep -q -i -F -f "$terms"; then echo "$f"; fi
  done)
  rm -f "$terms"
  if [ -n "$hits" ]; then
    echo "Private terms found in: $hits"; git reset -q; exit 1
  fi
fi
if git diff --cached --quiet; then echo "Nothing to publish."; exit 0; fi
git commit -q -m "${1:-Update the post}"
git push -q
echo "Pushed $(git rev-parse --short HEAD); the site updates in about a minute: https://runfme.github.io/claude-computer-use-trace/"
