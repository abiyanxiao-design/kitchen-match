const state = {
  user: null,
  dashboard: null,
  profile: null,
  publicFeed: null,
  authMode: "login",
  activeView: "feed",
  photoDataUrl: null,
  refreshIntervalId: null,
};

const authScreen = document.getElementById("auth-screen");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const showLoginButton = document.getElementById("show-login");
const showRegisterButton = document.getElementById("show-register");
const closeAuthButton = document.getElementById("close-auth");
const authMessage = document.getElementById("auth-message");
const logoutButton = document.getElementById("logout-button");

const heroTitle = document.getElementById("hero-title");
const heroCapacity = document.getElementById("hero-capacity");
const updatesBadge = document.getElementById("updates-badge");
const heroPoint1 = document.getElementById("hero-point-1");
const heroPoint2 = document.getElementById("hero-point-2");
const heroPoint3 = document.getElementById("hero-point-3");
const starterStack = document.getElementById("starter-stack");

const viewButtons = document.querySelectorAll("[data-view-target]");
const views = document.querySelectorAll("[data-view]");
const jumpButtons = document.querySelectorAll("[data-jump]");

const sameDishList = document.getElementById("same-dish-list");
const sameStyleList = document.getElementById("same-style-list");
const hotDishesList = document.getElementById("hot-dishes-list");
const newDishesList = document.getElementById("new-dishes-list");
const weeklyMatchList = document.getElementById("weekly-match-list");
const monthlyProfileList = document.getElementById("monthly-profile-list");
const sameDishCount = document.getElementById("same-dish-count");
const sameStyleCount = document.getElementById("same-style-count");
const sameDishHeading = document.getElementById("same-dish-heading");
const sameStyleHeading = document.getElementById("same-style-heading");

const relationshipList = document.getElementById("relationship-list");
const nextUpList = document.getElementById("next-up-list");
const affinityGrid = document.getElementById("affinity-grid");
const profileStats = document.getElementById("profile-stats");
const timelineList = document.getElementById("timeline-list");
const footprintTitle = document.getElementById("footprint-title");
const footprintNote = document.getElementById("footprint-note");
const footprintFavorites = document.getElementById("footprint-favorites");

const dishName = document.getElementById("dish-name");
const dishNote = document.getElementById("dish-note");
const dishPhoto = document.getElementById("dish-photo");
const photoPreview = document.getElementById("photo-preview");
const postButton = document.getElementById("post-card");
const MAX_UPLOAD_IMAGE_EDGE = 1200;
const JPEG_UPLOAD_QUALITY = 0.72;
const SECOND_PASS_MAX_EDGE = 1000;
const SECOND_PASS_JPEG_QUALITY = 0.65;
const MAX_UPLOAD_BYTES_BEFORE_SECOND_PASS = 1.8 * 1024 * 1024;
const sameDishBlock = sameDishList.closest(".inspiration-block");
const sameStyleBlock = sameStyleList.closest(".inspiration-block");

let toastTimerId = null;
let deferredInstallPrompt = null;
let installBanner = null;
let installButton = null;
let dismissInstallButton = null;
let installBannerDismissed = false;
let imageLightbox = null;
let serviceWorkerRefreshTriggered = false;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (payload.error) {
      throw new Error(payload.error);
    }
    if (response.status === 401) {
      throw new Error("登录状态过期，请重新登录");
    }
    if (response.status === 413) {
      throw new Error("图片太大，请换一张小一点的照片");
    }
    if (response.status === 415) {
      throw new Error("图片格式不支持，请换一张常见照片格式");
    }
    if (response.status >= 500) {
      throw new Error("服务器暂时开小差了，请稍后再试");
    }
    throw new Error("请求失败，请稍后再试");
  }
  return payload;
}

function clearAutoRefresh() {
  if (state.refreshIntervalId) {
    clearInterval(state.refreshIntervalId);
    state.refreshIntervalId = null;
  }
}

function isStandaloneMode() {
  return window.matchMedia?.("(display-mode: standalone)")?.matches || window.navigator.standalone === true;
}

function isMobileBrowser() {
  const ua = window.navigator.userAgent || "";
  return /android|iphone|ipad|ipod|mobile/i.test(ua);
}

function ensureInstallBanner() {
  if (installBanner) {
    return installBanner;
  }

  installBanner = document.createElement("aside");
  installBanner.className = "home-install-hint";
  installBanner.hidden = true;
  installBanner.innerHTML = `
    <div class="home-install-hint-content home-install-hint__copy">
      <p class="home-install-hint__title">📱 把 Kitchen Match 放到手机桌面</p>
      <p class="home-install-hint-text home-install-hint__intro">以后不用再找网址，点一下桌面图标就能打开。</p>
      <div class="home-install-hint-steps home-install-hint__steps">
        <p class="home-install-hint__step-text">① 点击下方分享按钮 <span class="home-install-hint__emoji">↗️</span></p>
        <p class="home-install-hint__step-text">② 选择 <span class="home-install-hint__emoji">🏠</span> 添加到主屏幕</p>
        <p class="home-install-hint__step-text">③ 完成</p>
      </div>
    </div>
    <div class="home-install-hint__actions">
      <button class="ghost-link home-install-hint__dismiss" type="button">知道了</button>
    </div>
  `;
  document.body.appendChild(installBanner);
  dismissInstallButton = installBanner.querySelector(".home-install-hint__dismiss");

  dismissInstallButton.addEventListener("click", () => {
    dismissInstallBanner();
  });

  return installBanner;
}

function hideInstallBanner() {
  if (installBanner) {
    installBanner.hidden = true;
  }
}

function dismissInstallBanner() {
  installBannerDismissed = true;
  hideInstallBanner();
}

function maybeShowInstallBanner() {
  if (installBannerDismissed || isStandaloneMode() || !isMobileBrowser()) {
    hideInstallBanner();
    return;
  }
  ensureInstallBanner();

  dismissInstallButton.textContent = "知道了";
  installBanner.hidden = false;
}

async function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) {
    return;
  }
  try {
    const registration = await navigator.serviceWorker.register(`/sw.js?v=20260607-v2`);

    if (registration.waiting) {
      showToast("新版本已更新，正在刷新…", "success");
      registration.waiting.postMessage({ type: "SKIP_WAITING" });
    }

    registration.addEventListener("updatefound", () => {
      const nextWorker = registration.installing;
      if (!nextWorker) {
        return;
      }
      nextWorker.addEventListener("statechange", () => {
        if (nextWorker.state === "installed" && navigator.serviceWorker.controller) {
          showToast("新版本已更新，正在刷新…", "success");
          nextWorker.postMessage({ type: "SKIP_WAITING" });
        }
      });
    });

    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (serviceWorkerRefreshTriggered) {
        return;
      }
      serviceWorkerRefreshTriggered = true;
      window.location.reload();
    });
  } catch (error) {
    console.error("[Kitchen Match] service worker register failed", error);
  }
}

function setGuestMode(isGuest) {
  document.body.classList.toggle("guest-mode", isGuest);
  logoutButton.hidden = isGuest;
}

function showAuthScreen(mode = "login", message = "") {
  setAuthMode(mode);
  authMessage.textContent = message;
  authScreen.hidden = false;
}

function hideAuthScreen() {
  authScreen.hidden = true;
  authMessage.textContent = "";
}

function startAutoRefresh() {
  clearAutoRefresh();
  if (!state.user) {
    return;
  }
  state.refreshIntervalId = setInterval(() => {
    refreshDashboardData({ silent: true });
  }, 15000);
}

function clonePersonCard(person) {
  const template = document.getElementById("person-card-template");
  const node = template.content.firstElementChild.cloneNode(true);
  node.querySelector(".name").textContent = person.name;
  node.querySelector(".meta").textContent = person.meta;
  return node;
}

function setAuthMode(mode) {
  state.authMode = mode;
  showLoginButton.classList.toggle("active", mode === "login");
  showRegisterButton.classList.toggle("active", mode === "register");
  loginForm.classList.toggle("active", mode === "login");
  registerForm.classList.toggle("active", mode === "register");
  authMessage.textContent = "";
}

function activateView(name) {
  state.activeView = name;
  viewButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.viewTarget === name);
  });
  views.forEach((view) => {
    view.classList.toggle("active", view.dataset.view === name);
  });
}

function formatCreatedAt(value) {
  if (!value) {
    return "最近发布";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "最近发布";
  }
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  if (sameDay) {
    return `今天 ${date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
  }
  return date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
}

function ensureToast() {
  let toast = document.getElementById("app-toast");
  if (toast) {
    return toast;
  }
  toast = document.createElement("div");
  toast.id = "app-toast";
  toast.className = "app-toast";
  document.body.appendChild(toast);
  return toast;
}

function showToast(message, tone = "default") {
  const toast = ensureToast();
  toast.textContent = message;
  toast.dataset.tone = tone;
  toast.classList.add("visible");
  clearTimeout(toastTimerId);
  toastTimerId = setTimeout(() => {
    toast.classList.remove("visible");
  }, 2200);
}

function ensureImageLightbox() {
  if (imageLightbox) {
    return imageLightbox;
  }
  imageLightbox = document.createElement("div");
  imageLightbox.className = "image-lightbox";
  imageLightbox.hidden = true;
  imageLightbox.innerHTML = `
    <div class="image-lightbox__backdrop" data-lightbox-close="true">
      <img class="image-lightbox__image" alt="" />
    </div>
  `;
  document.body.appendChild(imageLightbox);
  imageLightbox.addEventListener("click", (event) => {
    if (event.target instanceof HTMLElement && event.target.dataset.lightboxClose === "true") {
      closeImageLightbox();
    }
  });
  return imageLightbox;
}

function openImageLightbox(src, alt = "") {
  if (!src) {
    return;
  }
  const lightbox = ensureImageLightbox();
  const image = lightbox.querySelector(".image-lightbox__image");
  image.src = src;
  image.alt = alt;
  lightbox.hidden = false;
  document.body.classList.add("lightbox-open");
}

function closeImageLightbox() {
  if (!imageLightbox) {
    return;
  }
  imageLightbox.hidden = true;
  const image = imageLightbox.querySelector(".image-lightbox__image");
  image.removeAttribute("src");
  image.alt = "";
  document.body.classList.remove("lightbox-open");
}

function renderPreviewableImage(url, alt, className = "") {
  return `<img class="${className} previewable-image" src="${escapeHtml(url)}" alt="${escapeHtml(alt)}" data-preview-src="${escapeHtml(url)}" data-preview-alt="${escapeHtml(alt)}" />`;
}

function countSubmittedDishes(rawValue) {
  return String(rawValue || "")
    .split(/[\n,，]+/)
    .map((item) => item.trim())
    .filter(Boolean).length;
}

function setPostButtonLoading(isLoading, text = "看看今天和谁撞菜") {
  postButton.disabled = isLoading;
  postButton.classList.toggle("is-loading", isLoading);
  postButton.textContent = isLoading ? text : "看看今天和谁撞菜";
}

function getPrimaryMatchSummary(dashboard) {
  if (!dashboard) {
    return "今天还没人和你撞上，不过你已经留下了这一顿。";
  }
  const sameDishGroups = dashboard.grouped_matches?.same_dish || groupLegacyMatches(dashboard.same_dish_matches || [], "same_dish");
  const sameStyleGroups = dashboard.grouped_matches?.same_style || groupLegacyMatches(dashboard.same_style_matches || [], "same_style");
  const leadGroup = sameDishGroups[0] || sameStyleGroups[0];
  if (!leadGroup) {
    return "今天还没人和你撞上，不过你已经留下了这一顿。";
  }
  return `你和 ${leadGroup.count} 个人撞上了${leadGroup.label}！`;
}

function revealMatchResults() {
  [sameDishBlock, sameStyleBlock].forEach((block) => {
    if (!block) {
      return;
    }
    block.classList.remove("reveal-pulse");
    requestAnimationFrame(() => {
      block.classList.add("reveal-pulse");
    });
  });
}

function scrollToMatchResults() {
  const target = sameDishBlock || sameDishList;
  if (!target) {
    return;
  }
  target.scrollIntoView({ behavior: "smooth", block: "start" });
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("图片读取失败，请换一张再试"));
    reader.readAsDataURL(file);
  });
}

function dataUrlByteLength(dataUrl) {
  const [, base64 = ""] = String(dataUrl || "").split(",", 2);
  if (!base64) {
    return 0;
  }
  const padding = (base64.match(/=*$/) || [""])[0].length;
  return Math.floor((base64.length * 3) / 4) - padding;
}

function loadImageElement(dataUrl) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("图片压缩失败，请稍后再试"));
    image.src = dataUrl;
  });
}

function canvasToJpegDataUrl(canvas, quality = JPEG_UPLOAD_QUALITY) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error("图片压缩失败，请稍后再试"));
          return;
        }
        const reader = new FileReader();
        reader.onload = () => resolve({
          dataUrl: reader.result,
          size: blob.size,
        });
        reader.onerror = () => reject(new Error("图片压缩失败，请稍后再试"));
        reader.readAsDataURL(blob);
      },
      "image/jpeg",
      quality,
    );
  });
}

async function renderCompressedImage(image, maxEdge, quality) {
  const longestEdge = Math.max(image.naturalWidth, image.naturalHeight);

  if (!longestEdge) {
    throw new Error("图片处理失败，请换一张照片");
  }

  const scale = longestEdge > maxEdge ? maxEdge / longestEdge : 1;
  const targetWidth = Math.max(1, Math.round(image.naturalWidth * scale));
  const targetHeight = Math.max(1, Math.round(image.naturalHeight * scale));

  const canvas = document.createElement("canvas");
  canvas.width = targetWidth;
  canvas.height = targetHeight;
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("图片处理失败，请换一张照片");
  }

  context.drawImage(image, 0, 0, targetWidth, targetHeight);
  return canvasToJpegDataUrl(canvas, quality);
}

async function compressImageFile(file) {
  const originalDataUrl = await readFileAsDataUrl(file);
  const image = await loadImageElement(originalDataUrl);

  const firstPass = await renderCompressedImage(image, MAX_UPLOAD_IMAGE_EDGE, JPEG_UPLOAD_QUALITY);
  if (typeof firstPass.dataUrl !== "string") {
    throw new Error("图片处理失败，请换一张照片");
  }

  if (firstPass.size <= MAX_UPLOAD_BYTES_BEFORE_SECOND_PASS) {
    return firstPass;
  }

  const secondPassImage = await loadImageElement(firstPass.dataUrl);
  const secondPass = await renderCompressedImage(secondPassImage, SECOND_PASS_MAX_EDGE, SECOND_PASS_JPEG_QUALITY);
  if (typeof secondPass.dataUrl !== "string") {
    throw new Error("图片处理失败，请换一张照片");
  }
  return secondPass;
}

function getStarterDish(item) {
  const meta = String(item?.meta || "");
  if (!meta) {
    return "刚更新了一顿晚饭";
  }
  return meta.replace(/^刚发了\s*/, "").split("·")[0].trim() || "刚更新了一顿晚饭";
}

function renderStarterStack(items) {
  starterStack.innerHTML = "";
  const recentItems = (items || []).slice(0, 2);
  if (!recentItems.length) {
    const empty = document.createElement("p");
    empty.className = "starter-empty";
    empty.textContent = "还在等第一顿晚饭出现。";
    starterStack.appendChild(empty);
    return;
  }

  recentItems.forEach((item) => {
    const row = document.createElement("article");
    row.className = "starter-activity-row";
    row.innerHTML = `
      <span class="starter-activity-name">${escapeHtml(item.name)}</span>
      <span class="starter-activity-divider">·</span>
      <span class="starter-activity-dish">${escapeHtml(getStarterDish(item))}</span>
    `;
    starterStack.appendChild(row);
  });
}

function renderMatchEmptyState(target, emptyText) {
  target.innerHTML = "";
  const card = document.createElement("article");
  card.className = "match-empty-card card";
  card.innerHTML = `<p class="feed-note">${escapeHtml(emptyText)}</p>`;
  target.appendChild(card);
}

function renderGroupedMatchCards(target, groups, emptyText) {
  target.innerHTML = "";
  if (!groups.length) {
    renderMatchEmptyState(target, emptyText);
    return;
  }

  groups.forEach((group) => {
    const card = document.createElement("article");
    card.className = "match-group-card card";
    const previewNames = group.user_names.map((name) => `<span class="match-user-pill">${escapeHtml(name)}</span>`).join("");
    const morePeople = group.remaining_user_count
      ? `<span class="match-user-more">等 ${group.remaining_user_count} 人</span>`
      : "";
    const thumbnails = (group.thumbnails || [])
      .map((url, index) => renderPreviewableImage(url, `${group.label} ${index + 1}`))
      .join("");
    const detailPosts = (group.posts || [])
      .map((post) => {
        const imageMarkup = post.photo_data_url
          ? renderPreviewableImage(post.photo_data_url, post.dish)
          : "";
        return `
          <article class="match-detail-item">
            <div class="match-detail-head">
              <strong>${escapeHtml(post.author)}</strong>
              <span class="ghost-pill">${escapeHtml(post.created_day || post.audience)}</span>
            </div>
            <p class="match-detail-dish">${escapeHtml(post.dish)}</p>
            ${imageMarkup ? `<div class="match-detail-thumb">${imageMarkup}</div>` : ""}
            <p class="feed-note">${escapeHtml(post.note || "今天也做了这一顿。")}</p>
          </article>
        `;
      })
      .join("");

    card.innerHTML = `
      <div class="match-group-summary">
        <div>
          <p class="section-kicker">${escapeHtml(group.group_type)}</p>
          <h3>${escapeHtml(group.label)}</h3>
          <p class="feed-note match-summary-line">${escapeHtml(group.summary)}</p>
        </div>
        <span class="group-count">${group.count} 人</span>
      </div>
      <div class="match-user-list">
        ${previewNames}
        ${morePeople}
      </div>
      ${thumbnails ? `<div class="match-thumb-row">${thumbnails}</div>` : ""}
      <details class="match-details">
        <summary>查看详情</summary>
        <div class="match-detail-list">
          ${detailPosts}
        </div>
      </details>
    `;
    target.appendChild(card);
  });
}

function groupLegacyMatches(matches, groupType) {
  const grouped = new Map();

  matches.forEach((post) => {
    const key = groupType === "same_dish"
      ? (post.dish || "").trim()
      : (post.category || post.audience || "").trim();
    if (!key) {
      return;
    }

    if (!grouped.has(key)) {
      grouped.set(key, {
        group_key: key,
        group_type: groupType === "same_dish" ? "同一道菜" : "同一类菜",
        label: key,
        count: 0,
        summary: "",
        user_names: [],
        remaining_user_count: 0,
        thumbnails: [],
        posts: [],
      });
    }

    const group = grouped.get(key);
    group.count += 1;
    if (group.user_names.length < 5) {
      group.user_names.push(post.author);
    } else {
      group.remaining_user_count += 1;
    }
    if (post.photo_data_url && group.thumbnails.length < 3) {
      group.thumbnails.push(post.photo_data_url);
    }
    group.posts.push(post);
  });

  return Array.from(grouped.values())
    .map((group) => ({
      ...group,
      summary: `你和 ${group.count} 个人撞上了`,
    }))
    .sort((a, b) => b.count - a.count);
}

function renderPublicFeedCards(target, list, emptyText) {
  target.innerHTML = "";
  if (!list.length) {
    const card = document.createElement("article");
    card.className = "community-feed-card community-feed-empty card";
    card.innerHTML = `<p class="feed-note">${escapeHtml(emptyText)}</p>`;
    target.appendChild(card);
    return;
  }

  list.forEach((post) => {
    const card = document.createElement("article");
    card.className = "community-feed-card card";
    const imageMarkup = post.photo_public_url
      ? `<div class="community-feed-media">${renderPreviewableImage(post.photo_public_url, post.dish)}</div>`
      : `<div class="community-feed-media community-feed-media-empty"><span>${escapeHtml(post.dish)}</span></div>`;
    const noteMarkup = post.note
      ? `<p class="community-feed-note">${escapeHtml(post.note)}</p>`
      : "";
    card.innerHTML = `
      ${imageMarkup}
      <div class="community-feed-body">
        <div class="community-feed-meta-row">
          <span class="community-feed-meta">${escapeHtml(post.display_name)}</span>
          <span class="community-feed-meta">${escapeHtml(formatCreatedAt(post.created_at))}</span>
        </div>
        <h3 class="community-feed-dish">${escapeHtml(post.dish)}</h3>
        <div class="community-feed-subline">
          <span class="ghost-pill">${escapeHtml(post.category)}</span>
        </div>
        ${noteMarkup}
      </div>
    `;
    target.appendChild(card);
  });
}

function renderHotDishes(list) {
  hotDishesList.innerHTML = "";
  if (!list.length) {
    const card = document.createElement("article");
    card.className = "hot-dish-card hot-dish-empty card";
    card.innerHTML = `<p class="feed-note">今天还在等第一道菜出现。</p>`;
    hotDishesList.appendChild(card);
    return;
  }

  list.forEach((item, index) => {
    const card = document.createElement("article");
    card.className = "hot-dish-card card";
    const rank = ["🥇", "🥈", "🥉"][index] || "🍽️";
    const names = (item.user_names || []).join("、");
    const moreText = item.remaining_user_count ? ` 等 ${item.remaining_user_count} 人` : "";
    const thumbMarkup = item.thumbnail
      ? `<div class="hot-dish-thumb">${renderPreviewableImage(item.thumbnail, item.dish)}</div>`
      : `<div class="hot-dish-thumb hot-dish-thumb-empty">${rank}</div>`;

    card.innerHTML = `
      ${thumbMarkup}
      <div class="hot-dish-body">
        <div class="hot-dish-title-row">
          <strong>${rank} ${escapeHtml(item.dish)}</strong>
          <span class="ghost-pill">${escapeHtml(item.category)}</span>
        </div>
        <p class="hot-dish-meta">${escapeHtml(`${item.count} 人今天做了`)}</p>
        <p class="hot-dish-users">${escapeHtml(names)}${moreText ? `<span>${escapeHtml(moreText)}</span>` : ""}</p>
      </div>
    `;
    hotDishesList.appendChild(card);
  });
}

function renderNewDishes(list) {
  newDishesList.innerHTML = "";
  if (!list.length) {
    const card = document.createElement("article");
    card.className = "new-dish-card new-dish-empty card";
    card.innerHTML = `<p class="feed-note">今天的新灵感还在路上。</p>`;
    newDishesList.appendChild(card);
    return;
  }

  list.forEach((item) => {
    const card = document.createElement("article");
    card.className = "new-dish-card card";
    const thumbMarkup = item.photo_public_url
      ? `<div class="new-dish-thumb">${renderPreviewableImage(item.photo_public_url, item.dish)}</div>`
      : `<div class="new-dish-thumb new-dish-thumb-empty">🆕</div>`;
    const noteMarkup = item.note
      ? `<p class="new-dish-note">${escapeHtml(item.note)}</p>`
      : "";
    card.innerHTML = `
      ${thumbMarkup}
      <div class="new-dish-body">
        <div class="new-dish-head">
          <strong>${escapeHtml(item.dish)}</strong>
          <span class="ghost-pill">${escapeHtml(item.category)}</span>
        </div>
        <p class="new-dish-meta">${escapeHtml(item.display_name)} · ${escapeHtml(formatCreatedAt(item.created_at))}</p>
        ${noteMarkup}
      </div>
    `;
    newDishesList.appendChild(card);
  });
}

function renderPublicHome() {
  const data = state.publicFeed;
  if (!data) {
    return;
  }

  heroTitle.innerHTML = `
    <span class="hero-title-name">大家今晚</span>
    <span class="hero-title-question">吃了什么？</span>
  `;
  updatesBadge.textContent = `${data.updates_count} 人已更新`;
  heroCapacity.textContent = `最近已有 ${data.updates_count} 道晚饭`;
  heroPoint1.textContent = data.hero_points[0] || "先看看大家做了什么";
  heroPoint2.textContent = data.hero_points[1] || "想发一顿时再登录";
  heroPoint3.textContent = data.hero_points[2] || "撞菜和记录会在登录后开始";
  renderStarterStack(data.starters || []);
  renderHotDishes(data.today_hot_dishes || []);
  renderNewDishes(data.today_new_dishes || []);

  const publicLeadPosts = (data.today_posts && data.today_posts.length)
    ? data.today_posts
    : (data.recent_posts || []).slice(0, 8);
  const publicRecentPosts = (data.recent_posts || []).slice(0, 8);
  sameDishHeading.textContent = "🥘 大家今晚吃了什么";
  sameStyleHeading.textContent = "最近大家在做什么";
  sameDishCount.textContent = `${publicLeadPosts.length} 道`;
  sameStyleCount.textContent = `${publicRecentPosts.length} 道`;
  renderPublicFeedCards(sameDishList, publicLeadPosts, "今晚还没有新的晚饭更新。");
  renderPublicFeedCards(sameStyleList, publicRecentPosts, "最近还没有新的社区晚饭。");

  weeklyMatchList.innerHTML = "";
  (data.starters || []).forEach((person) => weeklyMatchList.appendChild(clonePersonCard(person)));

  monthlyProfileList.innerHTML = "";
  [
    "先看看社区里大家今晚吃了什么。",
    "你不登录也可以随便逛一逛。",
    "想发自己的晚饭时，再登录就行。",
  ].forEach((item) => {
    const card = document.createElement("article");
    card.className = "snapshot-item";
    card.innerHTML = `<strong>${escapeHtml(item)}</strong><p>先浏览，再决定要不要加入。</p>`;
    monthlyProfileList.appendChild(card);
  });
}

function renderDashboard() {
  const data = state.dashboard;
  if (!data) {
    return;
  }

  heroTitle.innerHTML = `
    <span class="hero-title-name">${escapeHtml(state.user.display_name)}</span>
    <span class="hero-title-question">今天做了什么？</span>
  `;
  updatesBadge.textContent = `${data.updates_count} 人已更新`;
  heroCapacity.textContent = `今天已有 ${data.updates_count} 人发了晚饭`;
  heroPoint1.textContent = data.hero_points[0] || "先写菜名";
  heroPoint2.textContent = data.hero_points[1] || "再看今天撞上谁";
  heroPoint3.textContent = data.hero_points[2] || "慢慢留下自己的记录";
  renderStarterStack(data.starters);
  renderHotDishes(data.today_hot_dishes || []);
  renderNewDishes(data.today_new_dishes || []);
  sameDishHeading.textContent = "撞上同一道菜";
  sameStyleHeading.textContent = "撞上同一类菜";

  const groupedSameDish = data.grouped_matches?.same_dish || [];
  const groupedSameStyle = data.grouped_matches?.same_style || [];
  const fallbackSameDish = groupLegacyMatches(data.same_dish_matches || [], "same_dish");
  const fallbackSameStyle = groupLegacyMatches(data.same_style_matches || [], "same_style");
  const sameDishGroups = groupedSameDish.length ? groupedSameDish : fallbackSameDish;
  const sameStyleGroups = groupedSameStyle.length ? groupedSameStyle : fallbackSameStyle;

  sameDishCount.textContent = `${sameDishGroups.length} 组`;
  sameStyleCount.textContent = `${sameStyleGroups.length} 组`;
  renderGroupedMatchCards(sameDishList, sameDishGroups, "今天还没有人和你撞上同一道菜。");
  renderGroupedMatchCards(sameStyleList, sameStyleGroups, "今天暂时没人和你做同一类菜。");

  weeklyMatchList.innerHTML = "";
  data.weekly_matches.forEach((person) => weeklyMatchList.appendChild(clonePersonCard(person)));

  monthlyProfileList.innerHTML = "";
  data.monthly_profiles.forEach((item) => {
    const card = document.createElement("article");
    card.className = "snapshot-item";
    card.innerHTML = `<strong>${escapeHtml(item)}</strong><p>这会慢慢形成你的厨房画像。</p>`;
    monthlyProfileList.appendChild(card);
  });
}

function renderProfile() {
  const data = state.profile;
  if (!data) {
    return;
  }

  const profileStatsData = data.profile_stats || {
    total_posts: 0,
    week_posts: 0,
    month_posts: 0,
    top_dishes: [],
    top_categories: [],
  };

  if (!profileStatsData.total_posts) {
    footprintTitle.textContent = "你的第一顿饭还在等你写下。";
    footprintNote.textContent = "从第一顿开始，慢慢会看到自己最常做什么、最近更爱吃什么。";
    footprintFavorites.innerHTML = `<p class="footprint-empty">先记下一顿，做饭足迹就会从这里开始。</p>`;
  } else {
    footprintTitle.textContent = `你已经认真吃了 ${profileStatsData.total_posts} 顿饭。`;
    footprintNote.textContent = `这周记下了 ${profileStatsData.week_posts} 顿，本月已经留下 ${profileStatsData.month_posts} 顿。`;
    const favoriteDishes = profileStatsData.top_dishes.length
      ? profileStatsData.top_dishes.map((item) => `${item.dish} ×${item.count}`).join("、")
      : "还在等你的招牌菜出现";
    footprintFavorites.innerHTML = `
      <div class="footprint-chip-row">
        <span class="footprint-chip">总记录 ${profileStatsData.total_posts} 顿</span>
        <span class="footprint-chip">本周 ${profileStatsData.week_posts} 顿</span>
        <span class="footprint-chip">本月 ${profileStatsData.month_posts} 顿</span>
      </div>
      <p class="footprint-favorite-line">最常做：${escapeHtml(favoriteDishes)}</p>
    `;
  }

  profileStats.innerHTML = "";
  data.stats.forEach((item) => {
    const card = document.createElement("article");
    card.className = "metric-card";
    card.innerHTML = `<span class="metric-label">${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong>`;
    profileStats.appendChild(card);
  });

  timelineList.innerHTML = "";
  data.timeline.forEach((item) => {
    const card = document.createElement("article");
    card.className = "timeline-item";
    const imageMarkup = item.photo_public_url
      ? `<div class="timeline-thumb">${renderPreviewableImage(item.photo_public_url, item.dish)}</div>`
      : "";
    card.innerHTML = `
      <div class="timeline-day">${escapeHtml(item.day)}</div>
      <div class="timeline-body">
        <strong>${escapeHtml(item.dish)}</strong>
        ${imageMarkup}
        <p>${escapeHtml(item.note)}</p>
      </div>
    `;
    timelineList.appendChild(card);
  });

  relationshipList.innerHTML = "";
  data.relationships.forEach((item) => relationshipList.appendChild(clonePersonCard(item)));

  nextUpList.innerHTML = "";
  data.next_up.forEach((item) => nextUpList.appendChild(clonePersonCard(item)));

  affinityGrid.innerHTML = "";
  data.affinities.forEach((item) => {
    const card = document.createElement("article");
    card.className = "affinity-card-item";
    card.innerHTML = `
      <strong>${escapeHtml(item.name)}</strong>
      <p>${escapeHtml(item.match)}</p>
      <p>${escapeHtml(item.text)}</p>
      <div class="affinity-tags">
        ${item.tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}
      </div>
    `;
    affinityGrid.appendChild(card);
  });
}

async function updatePhotoPreview(file) {
  if (!file) {
    state.photoDataUrl = null;
    photoPreview.classList.add("empty");
    photoPreview.innerHTML = "照片可选，不传也可以";
    return;
  }

  photoPreview.classList.add("empty");
  photoPreview.innerHTML = "正在准备照片...";

  try {
    console.log(`[Kitchen Match] original photo size: ${file.size} bytes`);
    const compressed = await compressImageFile(file);
    console.log(`[Kitchen Match] compressed photo size: ${compressed.size} bytes`);
    state.photoDataUrl = compressed.dataUrl;
    photoPreview.classList.remove("empty");
    photoPreview.innerHTML = `<img src="${compressed.dataUrl}" alt="你上传的菜图预览" />`;
    if (dataUrlByteLength(compressed.dataUrl) > MAX_UPLOAD_BYTES_BEFORE_SECOND_PASS) {
      console.warn("[Kitchen Match] compressed photo is still larger than target threshold");
    }
  } catch (_error) {
    state.photoDataUrl = null;
    dishPhoto.value = "";
    photoPreview.classList.add("empty");
    photoPreview.innerHTML = "照片可选，不传也可以";
    alert("图片处理失败，请换一张照片");
  }
}

async function refreshAppData() {
  const [dashboard, profile] = await Promise.all([
    fetchJson("/api/dashboard"),
    fetchJson("/api/profile"),
  ]);
  state.dashboard = dashboard;
  state.profile = profile;
  renderDashboard();
  renderProfile();
}

async function refreshPublicFeedData() {
  const publicFeed = await fetchJson("/api/public-feed");
  state.publicFeed = publicFeed;
  if (!state.user) {
    renderPublicHome();
  }
}

async function refreshDashboardData({ silent = false } = {}) {
  try {
    const dashboard = await fetchJson("/api/dashboard");
    state.dashboard = dashboard;
    renderDashboard();
  } catch (error) {
    if (!silent) {
      throw error;
    }
    if (String(error.message || "").includes("未登录")) {
      clearAutoRefresh();
    }
  }
}

async function bootstrap() {
  maybeShowInstallBanner();
  await refreshPublicFeedData().catch(() => {});
  try {
    const me = await fetchJson("/api/me");
    state.user = me.user;
    setGuestMode(false);
    hideAuthScreen();
    await refreshAppData();
    startAutoRefresh();
  } catch (_error) {
    clearAutoRefresh();
    state.user = null;
    state.dashboard = null;
    state.profile = null;
    setGuestMode(true);
    hideAuthScreen();
    activateView("feed");
    renderPublicHome();
  }
}

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstallPrompt = event;
  maybeShowInstallBanner();
});

window.addEventListener("appinstalled", () => {
  deferredInstallPrompt = null;
  hideInstallBanner();
  showToast("Kitchen Match 已经装到主屏幕了。", "success");
});

async function submitLogin(event) {
  event.preventDefault();
  authMessage.textContent = "登录中...";
  try {
    const payload = await fetchJson("/api/login", {
      method: "POST",
      body: JSON.stringify({
        email: document.getElementById("login-email").value.trim(),
        password: document.getElementById("login-password").value,
      }),
    });
    state.user = payload.user;
    setGuestMode(false);
    hideAuthScreen();
    authMessage.textContent = "";
    loginForm.reset();
    await refreshAppData();
    startAutoRefresh();
  } catch (error) {
    authMessage.textContent = error.message;
  }
}

async function submitRegister(event) {
  event.preventDefault();
  authMessage.textContent = "注册中...";
  try {
    const payload = await fetchJson("/api/register", {
      method: "POST",
      body: JSON.stringify({
        display_name: document.getElementById("register-name").value.trim(),
        email: document.getElementById("register-email").value.trim(),
        password: document.getElementById("register-password").value,
      }),
    });
    state.user = payload.user;
    setGuestMode(false);
    hideAuthScreen();
    authMessage.textContent = "";
    registerForm.reset();
    await refreshAppData();
    startAutoRefresh();
  } catch (error) {
    authMessage.textContent = error.message;
  }
}

async function logout() {
  await fetchJson("/api/logout", {
    method: "POST",
    body: JSON.stringify({}),
  }).catch(() => {});
  clearAutoRefresh();
  state.user = null;
  state.dashboard = null;
  state.profile = null;
  setGuestMode(true);
  hideAuthScreen();
  activateView("feed");
  await refreshPublicFeedData().catch(() => {});
}

async function postKitchenCard() {
  if (!state.user) {
    showAuthScreen("register", "想发自己的晚饭时，先登录或注册。");
    return;
  }
  const dish = dishName.value.trim();
  const note = dishNote.value.trim();
  if (!dish) {
    dishName.focus();
    alert("菜名不能为空");
    return;
  }

  try {
    setPostButtonLoading(true, "正在看看今天谁和你撞菜…");
    const submittedDishCount = countSubmittedDishes(dish);
    const payload = await fetchJson("/api/posts", {
      method: "POST",
      body: JSON.stringify({
        dish,
        note,
        photo_data_url: state.photoDataUrl,
      }),
    });
    const createdCount = payload.created_count || submittedDishCount || 1;
    showToast(`已记录 ${createdCount} 道菜，正在帮你看看和谁撞菜。`, "success");
    dishName.value = "";
    dishNote.value = "";
    dishPhoto.value = "";
    await updatePhotoPreview(null);
    await refreshAppData();
    await refreshPublicFeedData().catch(() => {});
    activateView("feed");
    startAutoRefresh();
    if (typeof navigator !== "undefined" && typeof navigator.vibrate === "function") {
      navigator.vibrate(30);
    }
    revealMatchResults();
    scrollToMatchResults();
    showToast(getPrimaryMatchSummary(state.dashboard), "accent");
    if (payload.warning) {
      showToast(payload.warning, "warning");
    }
  } catch (error) {
    if (String(error.message || "").includes("登录状态过期") || String(error.message || "").includes("请先登录")) {
      showAuthScreen("login", "登录状态过期，请重新登录。");
      setPostButtonLoading(false);
      return;
    }
    alert(error.message);
  } finally {
    setPostButtonLoading(false);
  }
}

showLoginButton.addEventListener("click", () => setAuthMode("login"));
showRegisterButton.addEventListener("click", () => setAuthMode("register"));
closeAuthButton.addEventListener("click", hideAuthScreen);
if (dismissInstallButton) {
  dismissInstallButton.addEventListener("click", () => {
    dismissInstallBanner();
  });
}
loginForm.addEventListener("submit", submitLogin);
registerForm.addEventListener("submit", submitRegister);
logoutButton.addEventListener("click", logout);

viewButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    const target = button.dataset.viewTarget;
    if (!state.user && target === "circle") {
      showAuthScreen("login", "登录后才能看自己的记录。");
      return;
    }
    activateView(target);
    if (target === "feed" && state.user) {
      try {
        await refreshDashboardData();
      } catch (error) {
        console.error(error);
      }
    }
  });
});

jumpButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const target = button.dataset.jump;
    if (target === "quick-post") {
      if (!state.user) {
        showAuthScreen("register", "想发一顿时，先登录或注册。");
        return;
      }
      activateView("feed");
      document.getElementById("quick-post").scrollIntoView({ behavior: "smooth", block: "start" });
      dishName.focus();
      return;
    }
    if (!state.user && target === "circle") {
      showAuthScreen("login", "登录后才能看自己的记录。");
      return;
    }
    activateView(target);
  });
});

document.getElementById("post-card").addEventListener("click", postKitchenCard);
document.getElementById("fill-demo").addEventListener("click", () => {
  dishName.value = "土豆烧鸡\n番茄炒蛋\n炒青菜";
  dishNote.value = "今天这个颜色终于对了，先把鸡肉煎一下，后面味道会更香。";
});

dishPhoto.addEventListener("change", (event) => {
  const [file] = event.target.files;
  updatePhotoPreview(file);
});

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) {
    return;
  }
  const image = target.closest("img[data-preview-src]");
  if (!image) {
    return;
  }
  openImageLightbox(image.dataset.previewSrc, image.dataset.previewAlt || image.getAttribute("alt") || "");
});

activateView("feed");
registerServiceWorker();
bootstrap();
