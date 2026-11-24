import { getStore } from "@netlify/blobs";
import { createHash } from "node:crypto";

/* Visit counter.
 *
 * Counts without cookies and without keeping anything that identifies a
 * person. A visitor's id is sha256(ip + user agent + today's date), truncated,
 * and the date is part of the hash on purpose: the same phone produces a
 * different id tomorrow, so the ids cannot be strung together into a history.
 * The raw IP is never written anywhere.
 *
 * One blob per event rather than a counter we read and rewrite. Blobs has no
 * atomic increment, so read-modify-write would quietly lose hits exactly when
 * traffic spikes - which is the moment the number matters. Writing a key per
 * event cannot collide, and the key alone carries everything /stats needs, so
 * counting never has to fetch a body.
 *
 *   v/<date>/<visitor hash>   unique visitors  (same key twice = still one)
 *   h/<date>/<random>         page views
 *   e/<date>/<name>/<random>  interactions: room switches, camera, share
 */

const DAY = () => new Date().toISOString().slice(0, 10);
const clean = s => String(s || "").replace(/[^a-zA-Z0-9._-]/g, "-").slice(0, 40);

export default async (req, context) => {
  if (req.method !== "POST") {
    return new Response("POST only", { status: 405 });
  }

  let body = {};
  try {
    body = await req.json();
  } catch {
    /* a beacon with no body still counts as a view */
  }

  const day = DAY();
  const store = getStore("visits");

  const ip = context?.ip
    || req.headers.get("x-nf-client-connection-ip")
    || req.headers.get("x-forwarded-for")
    || "";
  const ua = req.headers.get("user-agent") || "";
  const visitor = createHash("sha256").update(ip + "|" + ua + "|" + day)
    .digest("hex").slice(0, 16);

  const rand = Math.random().toString(36).slice(2, 10);
  const writes = [
    store.set(`v/${day}/${visitor}`, ""),
    store.set(`h/${day}/${rand}`, ""),
  ];

  const ev = clean(body.e);
  if (ev) writes.push(store.set(`e/${day}/${ev}/${rand}`, ""));

  // Referrer only when it is another site - our own pages say nothing useful.
  const ref = req.headers.get("referer") || "";
  try {
    const host = new URL(ref).hostname;
    if (host && !/(^|\.)gym-crowd\.netlify\.app$/.test(host) && host !== "localhost")
      writes.push(store.set(`r/${day}/${clean(host)}/${rand}`, ""));
  } catch {
    /* no referrer, or not a URL */
  }

  try {
    await Promise.all(writes);
  } catch (err) {
    // Never let counting break the page: the beacon ignores the reply anyway.
    console.error("hit: write failed", err);
    return new Response("", { status: 204 });
  }

  return new Response("", { status: 204 });
};

export const config = { path: "/api/hit" };
