#!/usr/bin/env python3
"""Scrape recsports.ufl.edu/about/hours/ into the HOURS block of index.html.

The hours page sends no Access-Control-Allow-Origin, so the dashboard cannot
read it from the browser on Netlify or in the artifact.  This script does the
read here and bakes the result in, so the page ships a schedule it can trust
and shows the date it was taken.  Re-run it when RecSports posts new adjusted
hours (they put up a fresh block each month):

    python3 hours.py && python3 build.py

Writes between the HOURS-DATA markers in index.html and nothing else.
"""
import datetime as dt
import html
import io
import json
import re
import sys
import urllib.request

URL = "https://recsports.ufl.edu/about/hours/"

# Facility heading on the page -> key used by the dashboard.
WANT = {
    "Southwest Recreation Center":            "SWRC",
    "Student Recreation & Fitness Center":    "SRFC",
    "UVS Sand Volleyball & Field Complex":    "UVS",
    "Southwest Recreation Center Tennis Courts": "TENNIS",
}

DAYNAMES = ["Sunday", "Monday", "Tuesday", "Wednesday",
            "Thursday", "Friday", "Saturday"]
DAYIX = {d.lower(): i for i, d in enumerate(DAYNAMES)}
MONTHS = {m.lower(): i for i, m in enumerate(
    ["", "January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}

DASH = "–—-"            # en dash, em dash, hyphen


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "hours-scraper"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def to_lines(src):
    src = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", src)
    src = re.sub(r"(?i)<br\s*/?>", "\n", src)
    src = re.sub(r"(?i)</(p|div|li|h[1-6]|td|tr|section)>", "\n", src)
    src = re.sub(r"<[^>]+>", "", src)
    src = html.unescape(src)
    return [l.strip() for l in src.split("\n") if l.strip()]


def parse_time(s):
    """'5:30 AM' / '8AM' / '12 AM' -> minutes from midnight. None if unparsed."""
    m = re.match(r"(?i)^\s*(\d{1,2})(?::(\d{2}))?\s*([AP])\.?M\.?\s*$", s)
    if not m:
        return None
    h, mins, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3).upper()
    if h == 12:
        h = 0
    if ap == "P":
        h += 12
    return h * 60 + mins


def parse_windows(val):
    """Right-hand side of an hours line -> [[open,close],...], or None if closed.

    Returns [] when the text is present but not a schedule we understand, so a
    caller can tell 'closed' from 'unreadable'.
    """
    v = val.strip().rstrip(".")
    if re.search(r"(?i)\bclosed\b", v):
        return None
    out = []
    # '11 AM - 1 PM; 7 PM - 9 PM' and '6:30 - 8:30 AM & 12 PM - 6 PM'
    for part in re.split(r"[;&]|,(?=\s*\d)", v):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"(?i)^(.+?)\s*[" + DASH + r"]\s*(.+)$", part)
        if not m:
            continue
        a, b = m.group(1).strip(), m.group(2).strip()
        close = parse_time(b)
        op = parse_time(a)
        if op is None and close is not None:
            # '6:30 - 8:30 AM': the opening time borrows the closing meridiem
            op = parse_time(a + re.sub(r"(?i)^.*?([AP]\.?M\.?)$", r" \1", b))
        if op is None or close is None:
            continue
        if close == 0:            # '12 AM' as a closing time is end of day
            close = 1440
        if close <= op:           # past midnight
            close += 1440
        out.append([op, close])
    return out


def parse_days(label):
    """'Monday - Friday' / 'Saturday, Sunday' / '7 Days a Week' -> [dow,...]."""
    lab = label.strip()
    if re.search(r"(?i)7\s*days|daily|every\s*day", lab):
        return list(range(7))
    m = re.match(r"(?i)^(\w+day)\s*[" + DASH + r"]\s*(\w+day)$", lab)
    if m:
        a, b = DAYIX.get(m.group(1).lower()), DAYIX.get(m.group(2).lower())
        if a is None or b is None:
            return []
        out, i = [], a
        while True:
            out.append(i)
            if i == b:
                break
            i = (i + 1) % 7
            if len(out) > 7:
                return []
        return out
    days = []
    for tok in re.split(r"[,&]|\band\b", lab):
        d = DAYIX.get(tok.strip().lower())
        if d is not None:
            days.append(d)
    return days


def parse_date(tok, year):
    m = re.match(r"(?i)^(?:\w+day,?\s*)?(\w+)\.?\s+(\d{1,2})$", tok.strip().strip(":,"))
    if not m:
        return None
    mon = MONTHS.get(m.group(1).lower())
    if not mon:
        return None
    try:
        return dt.date(year, mon, int(m.group(2)))
    except ValueError:
        return None


def parse_dated(label, year):
    """'Thursday, November 26 - Saturday, November 28' -> [date,...]."""
    lab = label.strip()
    m = re.match(r"^(.+?)\s*[" + DASH + r"]\s*(.+)$", lab)
    if m:
        a, b = parse_date(m.group(1), year), parse_date(m.group(2), year)
        if a and b and b >= a and (b - a).days <= 120:
            return [a + dt.timedelta(days=i) for i in range((b - a).days + 1)]
    out = []
    for tok in re.split(r"&|\band\b", lab):
        d = parse_date(tok, year)
        if d:
            out.append(d)
    return out


def section(lines, heading):
    """Lines of one facility block, from its heading to the next facility."""
    starts = [i for i, l in enumerate(lines) if l == heading
              and i + 1 < len(lines)
              and re.match(r"(?i)^(visit|learn more|closure notice)", lines[i + 1])]
    if not starts:
        return None
    i = starts[-1]
    heads = {h for h in WANT}
    j = i + 1
    while j < len(lines):
        nxt = lines[j]
        if (j + 1 < len(lines)
                and re.match(r"(?i)^(visit|learn more|closure notice)", lines[j + 1])
                and nxt != heading):
            break
        j += 1
    return lines[i:j]


def parse_section(body, year):
    weekly = [None] * 7           # None = not stated; [] = closed
    stated = [False] * 7
    adj = {}
    mode = None                   # 'weekly' | 'adjusted' | None
    for line in body:
        low = line.lower()
        if re.match(r"(?i)^summer hours", low):
            mode = "skip"          # we only ship the in-session schedule
            continue
        # 'Hours of Operation', but also 'Fall & Spring Hours of Operation'
        # and 'Sand Volleyball Hours of Operation' - the heading is qualified
        # differently on nearly every block.
        if re.match(r"(?i)^[\w &'\u2019-]*\bhours of operations?\b\s*:?", low):
            mode = "weekly"
            # '...Hours of Operation: 5:30 AM - 12 AM' puts the value inline
            rhs = line.split(":", 1)[1] if ":" in line else ""
            if rhs.strip():
                w = parse_windows(rhs)
                for d in range(7):
                    weekly[d], stated[d] = w, True
            continue
        if re.search(r"(?i)adjusted hours", low):
            mode = "adjusted"
            continue
        if ":" not in line:
            continue
        label, val = line.split(":", 1)
        if mode == "weekly":
            days = parse_days(label)
            if not days:
                continue
            w = parse_windows(val)
            for d in days:
                weekly[d], stated[d] = w, True
        elif mode == "adjusted":
            dates = parse_dated(label, year)
            if not dates:
                continue
            w = parse_windows(val)
            for d in dates:
                adj[d.isoformat()] = w
    for d in range(7):
        if not stated[d]:
            weekly[d] = None
    return {"weekly": weekly, "adj": dict(sorted(adj.items()))}


def main():
    src = fetch(URL)
    lines = to_lines(src)
    m = re.search(r"Copyright © (\d{4})", src)
    year = int(m.group(1)) if m else dt.date.today().year

    out = {}
    for heading, key in WANT.items():
        body = section(lines, heading)
        if not body:
            sys.exit("could not find the %r section - the page layout changed" % heading)
        out[key] = parse_section(body, year)
        out[key]["name"] = heading

    data = {
        "scraped": dt.date.today().isoformat(),
        "year": year,
        "src": URL,
        "fac": out,
    }

    path = "index.html"
    s = io.open(path, encoding="utf-8").read()
    a = "/* HOURS-DATA-START */"
    b = "/* HOURS-DATA-END */"
    if s.count(a) != 1 or s.count(b) != 1:
        sys.exit("index.html is missing the HOURS-DATA markers")
    block = a + "\nconst HOURS = " + json.dumps(data, indent=0).replace("\n", "") + ";\n" + b
    s = s[:s.index(a)] + block + s[s.index(b) + len(b):]
    io.open(path, "w", encoding="utf-8").write(s)

    for key, f in out.items():
        week = ", ".join(
            DAYNAMES[d][:3] + " " + ("-" if f["weekly"][d] is None else
                                     "closed" if f["weekly"][d] == [] else
                                     ",".join("%d:%02d-%d:%02d" % (w[0] // 60, w[0] % 60,
                                                                   w[1] // 60 % 24, w[1] % 60)
                                              for w in f["weekly"][d]))
            for d in range(7))
        print("%-7s %s" % (key, week))
        print("        %d adjusted date(s): %s" % (
            len(f["adj"]), ", ".join(sorted(f["adj"])[:4]) + (" ..." if len(f["adj"]) > 4 else "")))


if __name__ == "__main__":
    main()
