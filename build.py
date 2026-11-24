#!/usr/bin/env python3
"""Copy index.html to dist/ for Netlify.

index.html used to be artifact-shaped (no doctype/head/body) and this script
wrapped it. Since 2026-11-22 it is a complete document: the artifact publisher
now requires one too, so the same file serves both targets and there is nothing
left to wrap. Kept so the dist/ folder Netlify deploys from stays current.
"""
import io, os, shutil, sys

src = io.open("index.html", encoding="utf-8").read()
if not src.lstrip().lower().startswith("<!doctype html>"):
    sys.exit("index.html must be a complete document starting with <!DOCTYPE html>")
for tag in ("<html", "</html>", "<head>", "</head>", "<body>", "</body>"):
    if tag not in src.lower():
        sys.exit("index.html is missing %s" % tag)

os.makedirs("dist", exist_ok=True)
shutil.copyfile("index.html", "dist/index.html")
print("wrote dist/index.html  (%d bytes)" % len(src.encode("utf-8")))
