#!/bin/zsh
# Re-scrape the RecSports hours page, rebuild, and ship it if it still looks
# sane.  Run daily by ~/Library/LaunchAgents/com.mason.gymcrowd.hours.plist.
# Log: logs/refresh-hours.log
#
# Deploys every day, not only on a change, so the "as posted <date>" stamp on
# the page is always today's.  That stamp is the only thing telling a visitor
# how much to trust the holiday hours, so a stale one is worse than a deploy.

set -u
cd "${0:A:h}" || exit 1
mkdir -p logs
exec >> logs/refresh-hours.log 2>&1

# launchd hands us a bare PATH. The netlify CLI is `#!/usr/bin/env node`, and
# this Mac's Homebrew node is broken (dyld cannot find libsimdjson), so put
# nvm's node in front of it - the same one the interactive shell uses.
nvm_default="$(cat "$HOME/.nvm/alias/default" 2>/dev/null)"
nvm_bin=""
if [[ -n "$nvm_default" ]]; then
  nvm_bin="$(print -r -- "$HOME"/.nvm/versions/node/v${nvm_default}*/bin(N) | tail -1)"
fi
if [[ -z "$nvm_bin" ]]; then
  nvm_bin="$(print -rl -- "$HOME"/.nvm/versions/node/*/bin(N) | sort -V | tail -1)"
fi
export PATH="${nvm_bin:+$nvm_bin:}/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
say(){ print -r -- "$(date '+%Y-%m-%d %H:%M')  $*" }

say "--- start"

cp index.html .index.html.prev || { say "FAIL could not snapshot index.html"; exit 1 }
restore(){ mv .index.html.prev index.html; say "restored previous index.html" }

if ! python3 hours.py; then
  say "FAIL scrape failed - RecSports probably changed the page layout. Left the old hours in place."
  restore; exit 1
fi

# The scraper exits non-zero on a missing section, but a page that still has
# the headings and no times underneath would slip through, so check the result.
if ! python3 - <<'PY'
import io, json, re, sys
s = io.open("index.html", encoding="utf-8").read()
m = re.search(r"/\* HOURS-DATA-START \*/\nconst HOURS = (.*?);\n/\* HOURS-DATA-END \*/", s, re.S)
if not m: sys.exit("no HOURS block")
d = json.loads(m.group(1))
for k in ("SWRC", "SRFC", "UVS", "TENNIS"):
    f = d["fac"].get(k) or sys.exit("missing facility " + k)
    if not any(f["weekly"]): sys.exit(k + " has no weekly hours")
# the two weight rooms always carry dated overrides; zero means a parse failure
for k in ("SWRC", "SRFC"):
    if not d["fac"][k]["adj"]: sys.exit(k + " lost its adjusted-hours block")
print("sane: SWRC %d / SRFC %d adjusted dates"
      % (len(d["fac"]["SWRC"]["adj"]), len(d["fac"]["SRFC"]["adj"])))
PY
then
  say "FAIL parsed hours failed the sanity check. Nothing deployed."
  restore; exit 1
fi

if ! python3 build.py; then say "FAIL build"; restore; exit 1; fi

if diff -q .index.html.prev index.html >/dev/null; then
  say "hours unchanged"
else
  say "hours CHANGED"
fi
rm -f .index.html.prev

if netlify deploy --dir=dist --prod -m "hours refresh $(date '+%Y-%m-%d')" >/dev/null; then
  say "deployed to https://gym-crowd.netlify.app"
else
  say "FAIL deploy - is the netlify CLI still logged in? run: netlify status"
  exit 1
fi

say "--- done"
