import { getStore } from "@netlify/blobs";

/* The numbers, at /stats.
 *
 * Counting is done by listing keys - the keys carry the date, the visitor
 * hash and the event name, so nothing has to be fetched. Scoped to a window
 * of days so the listing stays small as the site ages.
 */

const DAYS = 30;

const iso = d => d.toISOString().slice(0, 10);
const esc = s => String(s).replace(/[&<>"]/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function countByDay(store, prefix) {
  const { blobs } = await store.list({ prefix });
  const out = new Map();
  for (const b of blobs) {
    // prefix/<day>/...  ->  the day is the segment after the prefix
    const day = b.key.slice(prefix.length).split("/")[0];
    if (day) out.set(day, (out.get(day) || 0) + 1);
  }
  return out;
}

async function countByName(store, prefix, since) {
  const { blobs } = await store.list({ prefix });
  const out = new Map();
  for (const b of blobs) {
    const [day, ...rest] = b.key.slice(prefix.length).split("/");
    if (!day || day < since || rest.length < 2) continue;
    const name = rest.slice(0, -1).join("/");
    out.set(name, (out.get(name) || 0) + 1);
  }
  return out;
}

export default async () => {
  const store = getStore("visits");
  const today = new Date();
  const days = [];
  for (let i = DAYS - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setUTCDate(d.getUTCDate() - i);
    days.push(iso(d));
  }
  const since = days[0];

  let visitors, views, events, refs;
  try {
    [visitors, views, events, refs] = await Promise.all([
      countByDay(store, "v/"),
      countByDay(store, "h/"),
      countByName(store, "e/", since),
      countByName(store, "r/", since),
    ]);
  } catch (err) {
    return new Response("Counting is not set up yet: " + err.message,
      { status: 500, headers: { "content-type": "text/plain" } });
  }

  const totalV = days.reduce((s, d) => s + (visitors.get(d) || 0), 0);
  const totalH = days.reduce((s, d) => s + (views.get(d) || 0), 0);
  const peak = Math.max(1, ...days.map(d => visitors.get(d) || 0));
  const allTimeV = [...visitors.values()].reduce((s, n) => s + n, 0);

  const rows = days.map(d => {
    const v = visitors.get(d) || 0, h = views.get(d) || 0;
    const w = Math.round((v / peak) * 100);
    return `<tr><td>${d}</td><td class=n>${v}</td><td class=n>${h}</td>
      <td class=bar><i style="width:${w}%"></i></td></tr>`;
  }).join("");

  const list = (m, empty) => {
    const e = [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12);
    return e.length
      ? e.map(([k, n]) => `<tr><td>${esc(k)}</td><td class=n>${n}</td></tr>`).join("")
      : `<tr><td colspan=2 class=dim>${empty}</td></tr>`;
  };

  const html = `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>UF Rec Crowd — visits</title>
<style>
  :root{--chalk:#E8E6E0;--iron:#1F1D1B;--steel:#6E6A64;--line:#C6C2B9;--green:#2F7D3A}
  body{background:var(--chalk);color:var(--iron);margin:0;padding:28px 20px 60px;
       font-family:ui-monospace,"SF Mono",Menlo,monospace;font-size:13px}
  .wrap{max-width:720px;margin:0 auto}
  h1{font-size:19px;margin:0 0 4px;letter-spacing:.02em}
  .sub{color:var(--steel);font-size:11px;margin:0 0 26px;letter-spacing:.08em;text-transform:uppercase}
  .big{display:flex;gap:40px;flex-wrap:wrap;margin:0 0 30px}
  .big div span{display:block;font-size:34px;font-weight:600;line-height:1}
  .big div em{font-style:normal;color:var(--steel);font-size:11px;
              letter-spacing:.08em;text-transform:uppercase}
  h2{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--steel);
     margin:30px 0 8px;font-weight:400}
  table{width:100%;border-collapse:collapse}
  td{padding:4px 8px 4px 0;border-bottom:1px solid var(--line);vertical-align:middle}
  .n{text-align:right;width:62px;font-variant-numeric:tabular-nums}
  .bar{width:46%}
  .bar i{display:block;height:9px;background:var(--green);min-width:0}
  .dim{color:var(--steel)}
  a{color:var(--steel)}
</style></head><body><div class="wrap">
<h1>UF Rec Crowd</h1>
<p class="sub">visits &middot; last ${DAYS} days</p>
<div class="big">
  <div><span>${totalV}</span><em>people</em></div>
  <div><span>${totalH}</span><em>page views</em></div>
  <div><span>${allTimeV}</span><em>people, all time</em></div>
</div>
<h2>By day &middot; people / views</h2>
<table>${rows}</table>
<h2>What people tapped</h2>
<table>${list(events, "nothing yet")}</table>
<h2>Where they came from</h2>
<table>${list(refs, "no outside referrers yet")}</table>
<p class="sub" style="margin-top:30px">
  A person is counted once a day. No cookies; the id is a hash of address and
  browser that changes daily, and the address itself is never stored.
  <a href="/">back to the dashboard</a>
</p>
</div></body></html>`;

  return new Response(html, {
    headers: { "content-type": "text/html; charset=utf-8",
               "cache-control": "no-store" },
  });
};

export const config = { path: "/stats" };
