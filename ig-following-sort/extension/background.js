const IG_COOKIE_URL = "https://www.instagram.com";
const IG_API_BASE = "https://i.instagram.com/api/v1";
const PAGE_SIZE = 200;
const PAGE_DELAY_MS = 800;
const CACHE_TTL_MS = 10 * 60 * 1000; // 10 minutes
const BIO_CACHE_TTL_MS = 3 * 24 * 60 * 60 * 1000; // 3 days
const BIO_DELAY_MS = 700;

// ---------------------------------------------------------------------------
// Cookie helpers
// ---------------------------------------------------------------------------

async function getIGCookies() {
  const names = ["ds_user_id", "csrftoken", "sessionid"];
  const results = {};
  for (const name of names) {
    const cookie = await chrome.cookies.get({ url: IG_COOKIE_URL, name });
    if (cookie) results[name] = cookie.value;
  }
  return results;
}

// ---------------------------------------------------------------------------
// API fetch with IG mobile headers
// ---------------------------------------------------------------------------

async function igFetch(path, cookies) {
  const url = `${IG_API_BASE}${path}`;
  const res = await fetch(url, {
    credentials: "include",
    headers: {
      "X-CSRFToken": cookies.csrftoken || "",
      "X-IG-App-ID": "936619743392459",
      "User-Agent":
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`IG API ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Paginated following fetch (with progress via port)
// ---------------------------------------------------------------------------

async function fetchAllFollowing(cookies, order, port) {
  const userId = cookies.ds_user_id;
  if (!userId) throw new Error("Not logged in – ds_user_id cookie missing");

  let allUsers = [];
  let maxId = null;
  let page = 0;

  while (true) {
    let path = `/friendships/${userId}/following/?count=${PAGE_SIZE}&order=${order}`;
    if (maxId) path += `&max_id=${maxId}`;

    const data = await igFetch(path, cookies);
    const users = data.users || [];
    allUsers = allUsers.concat(users);
    page++;

    if (port) {
      try {
        port.postMessage({ type: "PROGRESS", loaded: allUsers.length, page, hasMore: !!data.next_max_id });
      } catch (_) { /* port may have disconnected */ }
    }

    if (!data.next_max_id) break;
    maxId = data.next_max_id;

    await new Promise((r) => setTimeout(r, PAGE_DELAY_MS));
  }

  return allUsers;
}

// ---------------------------------------------------------------------------
// Image proxy – fetch an image URL in SW context and return as data-URL.
// The SW has no Referer header issues that plague extension popup <img> tags.
// ---------------------------------------------------------------------------

async function proxyImage(url) {
  const res = await fetch(url, { credentials: "omit" });
  if (!res.ok) throw new Error(`Image fetch ${res.status}`);
  const blob = await res.blob();
  const buf = await blob.arrayBuffer();
  const bytes = new Uint8Array(buf);
  let binary = "";
  const chunkSize = 8192;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  const contentType = blob.type || "image/jpeg";
  return `data:${contentType};base64,${btoa(binary)}`;
}

// ---------------------------------------------------------------------------
// Cache
// ---------------------------------------------------------------------------

async function getCached(order) {
  const key = `following_${order}`;
  const result = await chrome.storage.local.get([key, `${key}_ts`]);
  const data = result[key];
  const ts = result[`${key}_ts`];
  if (data && ts && Date.now() - ts < CACHE_TTL_MS) {
    return data;
  }
  return null;
}

async function setCache(order, users) {
  const key = `following_${order}`;
  await chrome.storage.local.set({ [key]: users, [`${key}_ts`]: Date.now() });
}

async function getBioCacheBatch(ids) {
  const keys = ids.map((id) => `bio_${id}`);
  const result = await chrome.storage.local.get(keys);
  const now = Date.now();
  const map = {};
  for (const id of ids) {
    const item = result[`bio_${id}`];
    if (!item || !item.ts) continue;
    if (now - item.ts > BIO_CACHE_TTL_MS) continue;
    map[id] = item;
  }
  return map;
}

async function setBioCacheOne(id, profile) {
  await chrome.storage.local.set({
    [`bio_${id}`]: {
      ...profile,
      ts: Date.now(),
    },
  });
}

async function fetchUserBio(cookies, userId) {
  const data = await igFetch(`/users/${userId}/info/`, cookies);
  const u = data?.user || {};
  return {
    biography: u.biography || "",
    category: u.category || "",
    city_name: u.city_name || "",
  };
}

// ---------------------------------------------------------------------------
// Message handler (simple request/response)
// ---------------------------------------------------------------------------

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "CHECK_LOGIN") {
    handleCheckLogin(sendResponse);
    return true;
  }
  if (msg.type === "PROXY_IMAGE") {
    proxyImage(msg.url)
      .then((dataUrl) => sendResponse({ ok: true, dataUrl }))
      .catch((e) => sendResponse({ ok: false, error: e.message }));
    return true;
  }
});

async function handleCheckLogin(sendResponse) {
  try {
    const cookies = await getIGCookies();
    sendResponse({
      ok: true,
      loggedIn: !!cookies.ds_user_id && !!cookies.sessionid,
      userId: cookies.ds_user_id || null,
    });
  } catch (e) {
    sendResponse({ ok: false, error: e.message });
  }
}

// ---------------------------------------------------------------------------
// Long-lived connection for FETCH_FOLLOWING (supports streaming progress)
// ---------------------------------------------------------------------------

chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== "following" && port.name !== "bios") return;

  port.onMessage.addListener(async (msg) => {
    if (msg.type === "FETCH_BIOS") {
      const ids = Array.isArray(msg.ids) ? msg.ids.filter(Boolean) : [];
      const parsed = Number(msg.limit);
      const limit = Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : ids.length;
      const targetIds = ids.slice(0, limit);

      try {
        const cookies = await getIGCookies();
        if (!cookies.ds_user_id || !cookies.sessionid) {
          port.postMessage({ type: "ERROR", error: "Not logged in to Instagram." });
          return;
        }

        const cached = await getBioCacheBatch(targetIds);
        const profiles = {};
        for (const id of Object.keys(cached)) {
          profiles[id] = {
            biography: cached[id].biography || "",
            category: cached[id].category || "",
            city_name: cached[id].city_name || "",
          };
        }

        const pendingIds = targetIds.filter((id) => !cached[id]);
        let processed = Object.keys(cached).length;
        let fetched = 0;
        let failed = 0;

        if (processed > 0) {
          port.postMessage({
            type: "BIO_PROGRESS",
            processed,
            fetched,
            failed,
            cached: processed,
            total: targetIds.length,
          });
        }

        for (const id of pendingIds) {
          try {
            const profile = await fetchUserBio(cookies, id);
            profiles[id] = profile;
            // Cache every successful profile immediately so results persist
            // even if popup closes or request flow is interrupted.
            await setBioCacheOne(id, profile);
            fetched++;
          } catch (_) {
            failed++;
          }
          processed++;
          port.postMessage({
            type: "BIO_PROGRESS",
            processed,
            fetched,
            failed,
            cached: Object.keys(cached).length,
            total: targetIds.length,
          });
          await new Promise((r) => setTimeout(r, BIO_DELAY_MS));
        }

        port.postMessage({
          type: "BIO_DONE",
          profiles,
          meta: {
            total: targetIds.length,
            fetched,
            cached: Object.keys(cached).length,
            failed,
          },
        });
      } catch (e) {
        try {
          port.postMessage({ type: "ERROR", error: e.message });
        } catch (_) { /* port disconnected */ }
      }
      return;
    }

    if (msg.type !== "FETCH_FOLLOWING") return;

    const order = msg.order || "date_followed_latest";
    const forceRefresh = msg.forceRefresh || false;

    try {
      if (!forceRefresh) {
        const cached = await getCached(order);
        if (cached) {
          port.postMessage({ type: "DONE", users: cached, fromCache: true });
          return;
        }
      }

      const cookies = await getIGCookies();
      if (!cookies.ds_user_id || !cookies.sessionid) {
        port.postMessage({ type: "ERROR", error: "Not logged in to Instagram." });
        return;
      }

      const users = await fetchAllFollowing(cookies, order, port);
      await setCache(order, users);
      port.postMessage({ type: "DONE", users, fromCache: false });
    } catch (e) {
      try {
        port.postMessage({ type: "ERROR", error: e.message });
      } catch (_) { /* port disconnected */ }
    }
  });
});
