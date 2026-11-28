#!/usr/bin/env python3
"""Copy the HOURS block out of index.html into hours.json.

The page loads hours.json from raw.githubusercontent.com when it opens, so the
daily refresh only has to commit this one file. That commit carries
[skip netlify], so keeping the hours fresh never costs a Netlify deploy.
Run after hours.py and check-hours.py.
"""
import io
import json
import re
import sys

s = io.open("index.html", encoding="utf-8").read()
m = re.search(r"/\* HOURS-DATA-START \*/\nconst HOURS = (.*?);\n/\* HOURS-DATA-END \*/", s, re.S)
if not m:
    sys.exit("no HOURS block in index.html")
d = json.loads(m.group(1))
io.open("hours.json", "w", encoding="utf-8").write(json.dumps(d, indent=1) + "\n")
print("wrote hours.json  (scraped %s)" % d["scraped"])
