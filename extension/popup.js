// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------
const $loginGate = document.getElementById("login-gate");
const $mainUI = document.getElementById("main-ui");
const $errorState = document.getElementById("error-state");
const $errorMsg = document.getElementById("error-msg");
const $retryBtn = document.getElementById("retry-btn");

const $search = document.getElementById("search");
const $searchClear = document.getElementById("search-clear");
const $sortOrder = document.getElementById("sort-order");
const $fetchBioBtn = document.getElementById("fetch-bio-btn");
const $refreshBtn = document.getElementById("refresh-btn");
const $totalCount = document.getElementById("total-count");
const $cacheHint = document.getElementById("cache-hint");
const $bioProgress = document.getElementById("bio-progress");
const $bioProgressFill = document.getElementById("bio-progress-fill");
const $bioProgressText = document.getElementById("bio-progress-text");

const $loading = document.getElementById("loading");
const $loadingText = document.getElementById("loading-text");
const $userList = document.getElementById("user-list");
const $emptyMsg = document.getElementById("empty-msg");
const $scrollTop = document.getElementById("scroll-top-btn");
const $listContainer = document.getElementById("list-container");

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let allUsers = [];
let filteredUsers = [];
let searchQuery = "";
let bioLoadedCount = 0;
let bioFilterRefreshTimer = null;
const userById = new Map();
const rowById = new Map();
const pendingBioDomUpdateIds = new Set();
let bioDomFlushRaf = 0;
let visibleBioSyncRaf = 0;
const BIO_LOCAL_CACHE_TTL_MS = 3 * 24 * 60 * 60 * 1000;

const PLACEHOLDER_AVATAR =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' fill='%23dbdbdb'/%3E%3Ccircle cx='32' cy='24' r='11' fill='%23fafafa'/%3E%3Cellipse cx='32' cy='52' rx='18' ry='14' fill='%23fafafa'/%3E%3C/svg%3E";

const avatarCache = new Map(); // url -> dataUrl

// ---------------------------------------------------------------------------
// Lazy avatar loading via IntersectionObserver
// ---------------------------------------------------------------------------
const avatarObserver = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      const img = entry.target;
      const originalUrl = img.dataset.src;
      if (!originalUrl) continue;

      avatarObserver.unobserve(img);
      loadAvatar(img, originalUrl);
    }
  },
  { root: $listContainer, rootMargin: "200px" }
);

async function loadAvatar(img, url) {
  // 1. Check in-memory cache
  const cached = avatarCache.get(url);
  if (cached) {
    img.src = cached;
    return;
  }

  // 2. Proxy through background service worker (preferred path)
  try {
    const res = await chrome.runtime.sendMessage({ type: "PROXY_IMAGE", url });
    if (res?.ok && res.dataUrl) {
      img.src = res.dataUrl;
      avatarCache.set(url, res.dataUrl);
      return;
    }
  } catch (_) { /* fall through */ }

  // 3. Fallback to direct URL load.
  // Some CDN regions may still allow direct image rendering in extension context.
  img.onerror = () => {
    img.onerror = null;
    img.src = PLACEHOLDER_AVATAR;
  };
  img.referrerPolicy = "no-referrer";
  img.src = url;
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
function init() {
  chrome.runtime.sendMessage({ type: "CHECK_LOGIN" }, (res) => {
    if (chrome.runtime.lastError) {
      showError("Cannot connect to extension background.");
      return;
    }
    if (!res || !res.ok || !res.loggedIn) {
      showLogin();
      return;
    }
    showMain();
    loadFollowing(false);
  });
}

// ---------------------------------------------------------------------------
// View switching
// ---------------------------------------------------------------------------
function showLogin() {
  $loginGate.classList.remove("hidden");
  $mainUI.classList.add("hidden");
  $errorState.classList.add("hidden");
}

function showMain() {
  $loginGate.classList.add("hidden");
  $mainUI.classList.remove("hidden");
  $errorState.classList.add("hidden");
}

function showError(msg) {
  $loginGate.classList.add("hidden");
  $mainUI.classList.add("hidden");
  $errorState.classList.remove("hidden");
  $errorMsg.textContent = msg;
}

function normalizeForSearch(text) {
  return (text || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function showBioProgress(percent) {
  if (!$bioProgress || !$bioProgressFill || !$bioProgressText) return;
  const safe = Math.max(0, Math.min(100, Math.round(percent)));
  $bioProgress.classList.remove("hidden");
  $bioProgressFill.style.width = `${safe}%`;
  $bioProgressText.textContent = `${safe}%`;
}

function hideBioProgress() {
  if (!$bioProgress || !$bioProgressFill || !$bioProgressText) return;
  $bioProgress.classList.add("hidden");
  $bioProgressFill.style.width = "0%";
  $bioProgressText.textContent = "0%";
}

function updateSearchClearButton() {
  if (!$searchClear) return;
  $searchClear.classList.toggle("hidden", !$search.value.trim());
}

function composeBioText(user) {
  return [user.category || "", user.city_name || "", user.biography || ""]
    .map((s) => (s || "").trim())
    .filter(Boolean)
    .join(" · ");
}

function rebuildUserMap() {
  userById.clear();
  for (const user of allUsers) {
    const id = String(user.pk || "");
    if (!id) continue;
    userById.set(id, user);
  }
}

function applyBioToUser(user, profile) {
  const hadBio = !!(user.biography || user.category || user.city_name);
  user.biography = profile.biography || "";
  user.category = profile.category || "";
  user.city_name = profile.city_name || "";
  const hasBio = !!(user.biography || user.category || user.city_name);
  return !hadBio && hasBio;
}

function isElementVisibleInContainer(el, container) {
  if (!el || !container) return false;
  const r = el.getBoundingClientRect();
  const c = container.getBoundingClientRect();
  return r.bottom > c.top && r.top < c.bottom;
}

function updateUserBioInDOM(userId, visibleOnly = false) {
  const row = rowById.get(String(userId));
  const user = userById.get(String(userId));
  if (!row || !user) return false;
  if (visibleOnly && !isElementVisibleInContainer(row, $listContainer)) return false;

  const bioText = composeBioText(user);
  row.title = bioText ? bioText.replaceAll(" · ", " | ") : `@${user.username}`;

  const bioLine = row.querySelector(".user-bio");
  if (!bioLine) return false;

  bioLine.textContent = bioText || "\u00A0";
  bioLine.classList.toggle("loaded", !!bioText);
  return true;
}

function flushPendingBioDomUpdates() {
  bioDomFlushRaf = 0;
  for (const id of pendingBioDomUpdateIds) {
    updateUserBioInDOM(id, true);
  }
  pendingBioDomUpdateIds.clear();
}

function queueBioDomUpdate(userId) {
  pendingBioDomUpdateIds.add(String(userId));
  if (bioDomFlushRaf) return;
  bioDomFlushRaf = requestAnimationFrame(flushPendingBioDomUpdates);
}

function syncVisibleBioRows() {
  visibleBioSyncRaf = 0;
  for (const [id, row] of rowById.entries()) {
    if (!isElementVisibleInContainer(row, $listContainer)) continue;
    updateUserBioInDOM(id, false);
  }
}

function scheduleVisibleBioSync() {
  if (visibleBioSyncRaf) return;
  visibleBioSyncRaf = requestAnimationFrame(syncVisibleBioRows);
}

function scheduleFilterRefresh() {
  if (!searchQuery.trim()) return;
  if (bioFilterRefreshTimer) return;
  bioFilterRefreshTimer = setTimeout(() => {
    bioFilterRefreshTimer = null;
    applyFilter();
  }, 220);
}

async function hydrateBiosFromLocalCache(limit = null) {
  const targets = allUsers
    .map((u) => String(u.pk || ""))
    .filter(Boolean)
    .slice(0, limit == null ? allUsers.length : limit);
  if (!targets.length) return 0;
  const targetSet = new Set(targets);

  const keys = targets.map((id) => `bio_${id}`);
  const result = await chrome.storage.local.get(keys);
  const now = Date.now();
  let loaded = 0;

  for (const user of allUsers) {
    const id = String(user.pk || "");
    if (!id || !targetSet.has(id)) continue;
    const item = result[`bio_${id}`];
    if (!item || !item.ts) continue;
    if (now - item.ts > BIO_LOCAL_CACHE_TTL_MS) continue;
    user.biography = item.biography || "";
    user.category = item.category || "";
    user.city_name = item.city_name || "";
    if (user.biography || user.category || user.city_name) loaded++;
  }
  return loaded;
}

// ---------------------------------------------------------------------------
// Data loading (long-lived port for streaming progress)
// ---------------------------------------------------------------------------
function loadFollowing(forceRefresh) {
  $loading.classList.remove("hidden");
  $loadingText.textContent = "Loading following list...";
  $userList.innerHTML = "";
  $emptyMsg.classList.add("hidden");
  $totalCount.textContent = "";
  $cacheHint.textContent = "";

  const order = $sortOrder.value;
  const port = chrome.runtime.connect({ name: "following" });

  port.onMessage.addListener(async (msg) => {
    if (msg.type === "PROGRESS") {
      $loadingText.textContent = `Loaded ${msg.loaded} accounts...${msg.hasMore ? "" : " finalizing"}`;
    }

    if (msg.type === "DONE") {
      $loading.classList.add("hidden");
      allUsers = msg.users || [];
      rebuildUserMap();
      bioLoadedCount = await hydrateBiosFromLocalCache();
      $totalCount.textContent = `${allUsers.length} following`;
      $cacheHint.textContent = `${msg.fromCache ? "(cached)" : "(fresh)"} · bio ${bioLoadedCount}/${allUsers.length}`;
      applyFilter();
      port.disconnect();
    }

    if (msg.type === "ERROR") {
      $loading.classList.add("hidden");
      showError(msg.error || "Unknown error");
      port.disconnect();
    }
  });

  port.postMessage({ type: "FETCH_FOLLOWING", order, forceRefresh });
}

// ---------------------------------------------------------------------------
// Search & filter
// ---------------------------------------------------------------------------
function applyFilter() {
  const q = normalizeForSearch(searchQuery.trim());
  if (!q) {
    filteredUsers = allUsers;
  } else {
    filteredUsers = allUsers.filter((u) => {
      const haystack = normalizeForSearch([
        u.username || "",
        u.full_name || "",
        u.biography || "",
        u.category || "",
        u.city_name || "",
      ].join(" "));
      return haystack.includes(q);
    });
  }
  renderList();
  updateFilterStatus();
}

function updateFilterStatus() {
  if (searchQuery.trim()) {
    $totalCount.textContent = `${filteredUsers.length} / ${allUsers.length} following`;
  } else {
    $totalCount.textContent = `${allUsers.length} following`;
  }
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------
function renderList() {
  $userList.innerHTML = "";
  rowById.clear();

  if (filteredUsers.length === 0 && allUsers.length > 0) {
    $emptyMsg.classList.remove("hidden");
    return;
  }
  $emptyMsg.classList.add("hidden");

  const fragment = document.createDocumentFragment();

  for (let i = 0; i < filteredUsers.length; i++) {
    const user = filteredUsers[i];
    const userId = String(user.pk || "");
    const globalIndex = allUsers.indexOf(user);

    const li = document.createElement("li");
    li.className = "user-item";
    if (userId) li.dataset.userId = userId;
    const bioText = composeBioText(user);
    li.title = bioText ? bioText.replaceAll(" · ", " | ") : `@${user.username}`;
    li.addEventListener("click", () => {
      chrome.tabs.create({ url: `https://www.instagram.com/${user.username}/` });
    });

    const indexSpan = document.createElement("span");
    indexSpan.className = "user-index";
    indexSpan.textContent = globalIndex + 1;

    const avatar = document.createElement("img");
    avatar.className = "user-avatar";
    avatar.src = PLACEHOLDER_AVATAR;
    avatar.referrerPolicy = "no-referrer";
    avatar.onerror = () => {
      avatar.onerror = null;
      avatar.src = PLACEHOLDER_AVATAR;
    };
    if (user.profile_pic_url) {
      avatar.dataset.src = user.profile_pic_url;
      avatarObserver.observe(avatar);
    }

    const info = document.createElement("div");
    info.className = "user-info";

    const nameLine = document.createElement("div");
    const usernameSpan = document.createElement("span");
    usernameSpan.className = "user-username";
    usernameSpan.textContent = user.username;
    nameLine.appendChild(usernameSpan);

    if (user.is_verified) {
      const badge = document.createElement("span");
      badge.className = "user-badge";
      nameLine.appendChild(badge);
    }
    if (user.is_private) {
      const priv = document.createElement("span");
      priv.className = "user-private";
      priv.textContent = "\uD83D\uDD12";
      nameLine.appendChild(priv);
    }

    const fullName = document.createElement("div");
    fullName.className = "user-fullname";
    fullName.textContent = user.full_name || "";

    const bioLine = document.createElement("div");
    bioLine.className = "user-bio";
    bioLine.textContent = bioText || "\u00A0";
    bioLine.classList.toggle("loaded", !!bioText);

    info.appendChild(nameLine);
    info.appendChild(fullName);
    info.appendChild(bioLine);

    li.appendChild(indexSpan);
    li.appendChild(avatar);
    li.appendChild(info);
    fragment.appendChild(li);
    if (userId) rowById.set(userId, li);
  }

  $userList.appendChild(fragment);
  scheduleVisibleBioSync();
}

function fetchBios() {
  if (!allUsers.length) return;

  const ids = allUsers
    .map((u) => String(u.pk || ""))
    .filter(Boolean);
  if (!ids.length) return;

  $fetchBioBtn.disabled = true;
  $cacheHint.textContent = `bio: 0 / ${ids.length} ...`;
  showBioProgress(0);

  const port = chrome.runtime.connect({ name: "bios" });
  port.onMessage.addListener((msg) => {
    if (msg.type === "BIO_PROGRESS") {
      if (msg.itemId && msg.profile) {
        const user = userById.get(String(msg.itemId));
        if (user) {
          const becameLoaded = applyBioToUser(user, msg.profile);
          if (becameLoaded) bioLoadedCount++;
          queueBioDomUpdate(msg.itemId);
          scheduleFilterRefresh();
        }
      }
      $cacheHint.textContent = `bio: ${msg.processed}/${msg.total} (new ${msg.fetched}, cache ${msg.cached}, fail ${msg.failed})`;
      const percent = msg.total > 0 ? (msg.processed / msg.total) * 100 : 0;
      showBioProgress(percent);
      return;
    }

    if (msg.type === "BIO_DONE") {
      const profiles = msg.profiles || {};
      for (const [key, profile] of Object.entries(profiles)) {
        const user = userById.get(String(key));
        if (!user) continue;
        applyBioToUser(user, profile || {});
      }
      for (const user of allUsers) {
        const key = String(user.pk || "");
        const p = profiles[key];
        if (!p) continue;
        queueBioDomUpdate(key);
      }

      bioLoadedCount = allUsers.filter((u) => u.biography || u.category || u.city_name).length;
      const meta = msg.meta || {};
      $cacheHint.textContent = `bio done: ${bioLoadedCount}/${allUsers.length} (new ${meta.fetched || 0}, cache ${meta.cached || 0}, fail ${meta.failed || 0})`;
      $fetchBioBtn.disabled = false;
      showBioProgress(100);
      setTimeout(() => hideBioProgress(), 1200);
      applyFilter();
      port.disconnect();
      return;
    }

    if (msg.type === "ERROR") {
      $cacheHint.textContent = `bio error: ${msg.error || "unknown"}`;
      $fetchBioBtn.disabled = false;
      hideBioProgress();
      port.disconnect();
    }
  });

  port.postMessage({ type: "FETCH_BIOS", ids });
}

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------

let searchTimeout = null;
$search.addEventListener("input", () => {
  updateSearchClearButton();
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    searchQuery = $search.value;
    applyFilter();
  }, 200);
});

if ($searchClear) {
  $searchClear.addEventListener("click", () => {
    $search.value = "";
    searchQuery = "";
    updateSearchClearButton();
    applyFilter();
    $search.focus();
  });
}

$sortOrder.addEventListener("change", () => {
  loadFollowing(false);
});

$refreshBtn.addEventListener("click", () => {
  loadFollowing(true);
});

if ($fetchBioBtn) {
  $fetchBioBtn.addEventListener("click", () => {
    fetchBios();
  });
}

$retryBtn.addEventListener("click", () => {
  showMain();
  loadFollowing(true);
});

if ($scrollTop) {
  $listContainer.addEventListener("scroll", () => {
    $scrollTop.classList.toggle("hidden", $listContainer.scrollTop < 300);
    scheduleVisibleBioSync();
  });
  $scrollTop.addEventListener("click", () => {
    $listContainer.scrollTo({ top: 0, behavior: "smooth" });
  });
}

// Kick off
updateSearchClearButton();
init();
