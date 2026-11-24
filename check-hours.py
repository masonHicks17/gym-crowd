#!/usr/bin/env python3
"""Refuse to ship a scrape that came out wrong.

hours.py already exits non-zero when a facility heading vanishes, but a page
that still has the headings with no times under them would sail through and
quietly wipe the schedule. Run this between hours.py and build.py.
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

for k in ("SWRC", "SRFC", "UVS", "TENNIS"):
    f = d["fac"].get(k)
    if not f:
        sys.exit("missing facility " + k)
    if not any(f["weekly"]):
        sys.exit(k + " has no weekly hours")

# The two weight rooms always carry a dated-override block; zero means the
# adjusted-hours parse broke, which is exactly the part people rely on.
for k in ("SWRC", "SRFC"):
    if not d["fac"][k]["adj"]:
        sys.exit(k + " lost its adjusted-hours block")

print("hours look sane: SWRC %d / SRFC %d adjusted dates"
      % (len(d["fac"]["SWRC"]["adj"]), len(d["fac"]["SRFC"]["adj"])))
