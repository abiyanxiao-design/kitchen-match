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

const countdown = document.getElementById("countdown");
const dishName = document.getElementById("dish-name");
const dishNote = document.getElementById("dish-note");
const dishPhoto = document.getElementById("dish-photo");
const photoPreview = document.getElementById("photo-preview");

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
    throw new Error(payload.error || "请求失败");
  }
  return payload;
}

function clearAutoRefresh() {
  if (state.refreshIntervalId) {
    clearInterval(state.refreshIntervalId);
    state.refreshIntervalId = null;
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

function renderStarterStack(items) {
  starterStack.innerHTML = "";
  items.forEach((item) => starterStack.appendChild(clonePersonCard(item)));
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
      .map((url, index) => `<img src="${escapeHtml(url)}" alt="${escapeHtml(group.label)} ${index + 1}" />`)
      .join("");
    const detailPosts = (group.posts || [])
      .map((post) => {
        const imageMarkup = post.photo_data_url
          ? `<img src="${escapeHtml(post.photo_data_url)}" alt="${escapeHtml(post.dish)}" />`
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
    card.className = "feed-card card";
    card.innerHTML = `<p class="feed-note">${escapeHtml(emptyText)}</p>`;
    target.appendChild(card);
    return;
  }

  list.forEach((post) => {
    const card = document.createElement("article");
    card.className = "feed-card card";
    const imageMarkup = post.photo_public_url
      ? `<img src="${post.photo_public_url}" alt="${escapeHtml(post.dish)}" />`
      : `<span>${escapeHtml(post.dish)}</span>`;
    card.innerHTML = `
      <div class="feed-topline">
        <div>
          <p class="section-kicker">${escapeHtml(post.display_name)}</p>
          <h3>${escapeHtml(post.dish)}</h3>
        </div>
        <span class="ghost-pill">${escapeHtml(post.category)}</span>
      </div>
      <div class="feed-photo">${imageMarkup}</div>
      <p class="feed-note">${escapeHtml(post.note || "今天也做了这一顿。")}</p>
      <div class="comment-list">
        <div class="comment-item">${escapeHtml(formatCreatedAt(post.created_at))}</div>
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
      ? `<div class="hot-dish-thumb"><img src="${escapeHtml(item.thumbnail)}" alt="${escapeHtml(item.dish)}" /></div>`
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

  sameDishHeading.textContent = "大家今晚吃了什么";
  sameStyleHeading.textContent = "最近大家在做什么";
  sameDishCount.textContent = `${(data.today_posts || []).length} 道`;
  sameStyleCount.textContent = `${(data.recent_posts || []).length} 道`;
  renderPublicFeedCards(sameDishList, data.today_posts || [], "今晚还没有新的晚饭更新。");
  renderPublicFeedCards(sameStyleList, data.recent_posts || [], "最近还没有新的社区晚饭。");

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
    card.innerHTML = `
      <div class="timeline-day">${escapeHtml(item.day)}</div>
      <div class="timeline-body">
        <strong>${escapeHtml(item.dish)}</strong>
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

function updatePhotoPreview(file) {
  if (!file) {
    state.photoDataUrl = null;
    photoPreview.classList.add("empty");
    photoPreview.innerHTML = "照片可选，不传也可以";
    return;
  }

  const reader = new FileReader();
  reader.onload = () => {
    state.photoDataUrl = reader.result;
    photoPreview.classList.remove("empty");
    photoPreview.innerHTML = `<img src="${reader.result}" alt="你上传的菜图预览" />`;
  };
  reader.readAsDataURL(file);
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
    return;
  }

  try {
    await fetchJson("/api/posts", {
      method: "POST",
      body: JSON.stringify({
        dish,
        note,
        photo_data_url: state.photoDataUrl,
      }),
    });
    dishName.value = "";
    dishNote.value = "";
    dishPhoto.value = "";
    updatePhotoPreview(null);
    await refreshAppData();
    await refreshPublicFeedData().catch(() => {});
    activateView("feed");
    startAutoRefresh();
  } catch (error) {
    alert(error.message);
  }
}

showLoginButton.addEventListener("click", () => setAuthMode("login"));
showRegisterButton.addEventListener("click", () => setAuthMode("register"));
closeAuthButton.addEventListener("click", hideAuthScreen);
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
  dishName.value = "土豆烧鸡";
  dishNote.value = "今天这个颜色终于对了，先把鸡肉煎一下，后面味道会更香。";
});

dishPhoto.addEventListener("change", (event) => {
  const [file] = event.target.files;
  updatePhotoPreview(file);
});

activateView("feed");
bootstrap();
