const list = document.getElementById("unknown-dishes-list");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function fetchJson(url) {
  const response = await fetch(url, {
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || "加载失败，请稍后再试");
  }
  return payload;
}

function renderUnknownDishes(items) {
  list.innerHTML = "";

  if (!items.length) {
    list.innerHTML = `<p class="learning-empty">最近 30 天暂时没有新的“其他家常”。</p>`;
    return;
  }

  items.forEach((item, index) => {
    const row = document.createElement("article");
    row.className = "learning-unknown-item";
    row.innerHTML = `
      <span class="learning-unknown-dish">${escapeHtml(`${index + 1}. ${item.dish}`)}</span>
      <span class="learning-unknown-count">${escapeHtml(item.count)} 次</span>
    `;
    list.appendChild(row);
  });
}

async function bootstrap() {
  list.innerHTML = `<p class="learning-empty">正在加载...</p>`;
  try {
    const payload = await fetchJson("/api/admin/unknown-dishes");
    renderUnknownDishes(payload.items || []);
  } catch (error) {
    list.innerHTML = `<p class="learning-empty">${escapeHtml(error.message || "加载失败，请稍后再试")}</p>`;
  }
}

bootstrap();
