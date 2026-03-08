// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------
const $loginGate = document.getElementById("login-gate");
const $mainUI = document.getElementById("main-ui");
const $errorState = document.getElementById("error-state");
const $errorMsg = document.getElementById("error-msg");
const $retryBtn = document.getElementById("retry-btn");

const $search = document.getElementById("search");
const $sortOrder = document.getElementById("sort-order");
const $refreshBtn = document.getElementById("refresh-btn");
const $totalCount = document.getElementById("total-count");
const $cacheHint = document.getElementById("cache-hint");

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

  port.onMessage.addListener((msg) => {
    if (msg.type === "PROGRESS") {
      $loadingText.textContent = `Loaded ${msg.loaded} accounts...${msg.hasMore ? "" : " finalizing"}`;
    }

    if (msg.type === "DONE") {
      $loading.classList.add("hidden");
      allUsers = msg.users || [];
      $totalCount.textContent = `${allUsers.length} following`;
      $cacheHint.textContent = msg.fromCache ? "(cached)" : "(fresh)";
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
  const q = searchQuery.trim().toLowerCase();
  if (!q) {
    filteredUsers = allUsers;
  } else {
    filteredUsers = allUsers.filter((u) => {
      const haystack = [u.username || "", u.full_name || ""].join(" ").toLowerCase();
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

  if (filteredUsers.length === 0 && allUsers.length > 0) {
    $emptyMsg.classList.remove("hidden");
    return;
  }
  $emptyMsg.classList.add("hidden");

  const fragment = document.createDocumentFragment();

  for (let i = 0; i < filteredUsers.length; i++) {
    const user = filteredUsers[i];
    const globalIndex = allUsers.indexOf(user);

    const li = document.createElement("li");
    li.className = "user-item";
    li.title = `Open @${user.username} on Instagram`;
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

    info.appendChild(nameLine);
    info.appendChild(fullName);

    li.appendChild(indexSpan);
    li.appendChild(avatar);
    li.appendChild(info);
    fragment.appendChild(li);
  }

  $userList.appendChild(fragment);
}

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------

let searchTimeout = null;
$search.addEventListener("input", () => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    searchQuery = $search.value;
    applyFilter();
  }, 200);
});

$sortOrder.addEventListener("change", () => {
  loadFollowing(false);
});

$refreshBtn.addEventListener("click", () => {
  loadFollowing(true);
});

$retryBtn.addEventListener("click", () => {
  showMain();
  loadFollowing(true);
});

if ($scrollTop) {
  $listContainer.addEventListener("scroll", () => {
    $scrollTop.classList.toggle("hidden", $listContainer.scrollTop < 300);
  });
  $scrollTop.addEventListener("click", () => {
    $listContainer.scrollTo({ top: 0, behavior: "smooth" });
  });
}

// Kick off
init();
