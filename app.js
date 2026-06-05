const state = {
  user: null,
  dashboard: null,
  profile: null,
  authMode: "login",
  activeView: "feed",
  photoDataUrl: null,
};

const authScreen = document.getElementById("auth-screen");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const showLoginButton = document.getElementById("show-login");
const showRegisterButton = document.getElementById("show-register");
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
const weeklyMatchList = document.getElementById("weekly-match-list");
const monthlyProfileList = document.getElementById("monthly-profile-list");
const sameDishCount = document.getElementById("same-dish-count");
const sameStyleCount = document.getElementById("same-style-count");

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

function setAuthOnly(isAuthOnly) {
  document.body.classList.toggle("auth-only", isAuthOnly);
  authScreen.hidden = !isAuthOnly;
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

function renderStarterStack(items) {
  starterStack.innerHTML = "";
  items.forEach((item) => starterStack.appendChild(clonePersonCard(item)));
}

function renderMatchCards(target, list, emptyText) {
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
    const imageMarkup = post.photo_data_url
      ? `<img src="${post.photo_data_url}" alt="${escapeHtml(post.dish)}" />`
      : `<span>${escapeHtml(post.dish)}</span>`;

    card.innerHTML = `
      <div class="feed-topline">
        <div>
          <p class="section-kicker">${escapeHtml(post.author)}</p>
          <h3>${escapeHtml(post.dish)}</h3>
        </div>
        <span class="ghost-pill">${escapeHtml(post.audience)}</span>
      </div>
      <div class="feed-photo">${imageMarkup}</div>
      <p class="feed-note">${escapeHtml(post.note)}</p>
      <div class="comment-list">
        ${post.comments.map((comment) => `<div class="comment-item">${escapeHtml(comment)}</div>`).join("")}
      </div>
    `;
    target.appendChild(card);
  });
}

function renderDashboard() {
  const data = state.dashboard;
  if (!data) {
    return;
  }

  heroTitle.textContent = `${state.user.display_name}，今天做了什么？`;
  updatesBadge.textContent = `${data.updates_count} 人已更新`;
  heroCapacity.textContent = `今天已有 ${data.updates_count} 人发了晚饭`;
  heroPoint1.textContent = data.hero_points[0] || "先写菜名";
  heroPoint2.textContent = data.hero_points[1] || "再看今天撞上谁";
  heroPoint3.textContent = data.hero_points[2] || "慢慢留下自己的记录";
  renderStarterStack(data.starters);

  sameDishCount.textContent = `${data.same_dish_matches.length} 人`;
  sameStyleCount.textContent = `${data.same_style_matches.length} 人`;
  renderMatchCards(sameDishList, data.same_dish_matches, "今天还没有人和你撞上同一道菜。");
  renderMatchCards(sameStyleList, data.same_style_matches, "今天暂时没人和你做同一类菜。");

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

async function bootstrap() {
  try {
    const me = await fetchJson("/api/me");
    state.user = me.user;
    setAuthOnly(false);
    await refreshAppData();
  } catch (_error) {
    setAuthOnly(true);
    setAuthMode("login");
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
    setAuthOnly(false);
    authMessage.textContent = "";
    loginForm.reset();
    await refreshAppData();
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
    setAuthOnly(false);
    authMessage.textContent = "";
    registerForm.reset();
    await refreshAppData();
  } catch (error) {
    authMessage.textContent = error.message;
  }
}

async function logout() {
  await fetchJson("/api/logout", {
    method: "POST",
    body: JSON.stringify({}),
  }).catch(() => {});
  state.user = null;
  state.dashboard = null;
  state.profile = null;
  setAuthOnly(true);
  setAuthMode("login");
}

async function postKitchenCard() {
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
    activateView("feed");
  } catch (error) {
    alert(error.message);
  }
}

showLoginButton.addEventListener("click", () => setAuthMode("login"));
showRegisterButton.addEventListener("click", () => setAuthMode("register"));
loginForm.addEventListener("submit", submitLogin);
registerForm.addEventListener("submit", submitRegister);
logoutButton.addEventListener("click", logout);

viewButtons.forEach((button) => {
  button.addEventListener("click", () => activateView(button.dataset.viewTarget));
});

jumpButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const target = button.dataset.jump;
    if (target === "quick-post") {
      activateView("feed");
      document.getElementById("quick-post").scrollIntoView({ behavior: "smooth", block: "start" });
      dishName.focus();
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
