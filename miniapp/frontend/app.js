const tg = window.Telegram?.WebApp;
tg?.ready();
tg?.expand();

const STATUS_LABELS = {
  watching: "Смотрю",
  planned: "В планах",
  completed: "Просмотрено",
  on_hold: "Отложено",
  dropped: "Брошено",
};
const TYPE_LABELS = { anime: "Аниме", movie: "Фильм", tv: "Сериал" };

const view = document.getElementById("view");
const searchForm = document.getElementById("search-form");
const searchInput = document.getElementById("search-input");
const topbar = document.querySelector(".topbar");

const state = { type: "all", query: "", listStatus: "watching" };

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  if (tg?.initData) headers.Authorization = `tma ${tg.initData}`;
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Ошибка ${response.status}`);
  }
  return response.json();
}

function toast(text) {
  const element = document.createElement("div");
  element.className = "toast";
  element.textContent = text;
  document.body.append(element);
  setTimeout(() => element.remove(), 2200);
}

function haptic(kind = "light") {
  tg?.HapticFeedback?.impactOccurred(kind);
}

function spinner() {
  view.innerHTML = '<div class="spinner"></div>';
}

function showError(error) {
  view.innerHTML = `<div class="empty">${esc(error.message)}</div>`;
}

function posterHtml(item, withBadges = true) {
  const image = item.poster
    ? `<img src="${esc(item.poster)}" alt="" loading="lazy">`
    : '<div class="noimg">🎬</div>';
  const badges = withBadges
    ? `<span class="badge">${esc(TYPE_LABELS[item.type] || "")}</span>` +
      (item.score ? `<span class="badge score">★ ${esc(item.score)}</span>` : "")
    : "";
  return `<div class="poster">${image}${badges}</div>`;
}

function gridHtml(items) {
  if (!items.length) return '<div class="empty">Ничего не найдено</div>';
  return `<div class="grid">${items.map((item) => `
    <button class="card" data-key="${esc(item.key)}">
      ${posterHtml(item)}
      <div class="card-title">${esc(item.title)}</div>
      <div class="card-meta">${esc([item.year, item.kind || STATUS_LABELS[item.status]].filter(Boolean).join(" · "))}</div>
    </button>`).join("")}</div>`;
}

view.addEventListener("click", (event) => {
  const card = event.target.closest(".card[data-key]");
  if (card) navigate(`#/media/${card.dataset.key}`);
});

async function renderHome() {
  topbar.hidden = false;
  spinner();
  try {
    if (state.query) {
      const data = await api(`/api/search?q=${encodeURIComponent(state.query)}&type=${state.type}`);
      view.innerHTML = `<div class="section-title">Результаты поиска</div>${gridHtml(data.items)}`;
    } else {
      const data = await api(`/api/trending?type=${state.type}`);
      view.innerHTML = `<div class="section-title">Популярное сейчас</div>${gridHtml(data.items)}`;
    }
  } catch (error) {
    showError(error);
  }
}

async function renderRandom() {
  spinner();
  try {
    const item = await api(`/api/random?type=${state.type}`);
    haptic("medium");
    navigate(`#/media/${item.key}`, true);
  } catch (error) {
    showError(error);
  }
}

async function renderList() {
  topbar.hidden = true;
  spinner();
  try {
    const data = await api(`/api/list?status=${state.listStatus}`);
    const tabs = Object.entries(STATUS_LABELS).map(([status, label]) => {
      const count = data.stats[status] || 0;
      return `<button class="chip ${status === state.listStatus ? "active" : ""}" data-status="${status}">${label} ${count}</button>`;
    }).join("");
    const items = data.items.map((entry) => ({ ...entry, score: entry.score }));
    view.innerHTML = `<div class="list-tabs">${tabs}</div>` +
      (items.length ? gridHtml(items) : '<div class="empty">Здесь пока пусто</div>');
    view.querySelectorAll("[data-status]").forEach((button) => {
      button.addEventListener("click", () => {
        state.listStatus = button.dataset.status;
        renderList();
      });
    });
  } catch (error) {
    showError(error);
  }
}

function factsHtml(item) {
  const facts = [
    ["Тип", item.kind],
    ["Год", item.year],
    ["Статус", item.status],
    ["Сезонов", item.seasons],
    ["Эпизодов", item.episodes],
    ["Длительность", item.duration ? `${item.duration} мин.` : null],
    [item.type === "tv" || item.type === "anime" ? "Студия" : "Производство", item.studios?.join(", ")],
    ["Рейтинг", item.score ? `★ ${item.score}` : null],
  ];
  return facts.filter(([, value]) => value).map(([label, value]) => `<div>${label}: <b>${esc(value)}</b></div>`).join("");
}

function trailersHtml(trailers) {
  if (!trailers.length) return "";
  const tabs = trailers.length > 1
    ? `<div class="trailer-tabs">${trailers.map((trailer, index) =>
        `<button class="chip ${index === 0 ? "active" : ""}" data-trailer="${esc(trailer.youtube_id)}">${esc(trailer.name)}</button>`).join("")}</div>`
    : "";
  return `<div class="block"><h2>Трейлеры</h2>${tabs}
    <iframe class="trailer" src="https://www.youtube-nocookie.com/embed/${esc(trailers[0].youtube_id)}"
      allow="autoplay; encrypted-media; picture-in-picture; fullscreen" loading="lazy"></iframe></div>`;
}

function watchHtml(item) {
  if (item.type === "anime") return "";
  if (!item.watch.length) {
    return '<div class="block"><h2>Где посмотреть</h2><div class="hint">Легальных площадок в вашем регионе не найдено</div></div>';
  }
  return `<div class="block"><h2>Где посмотреть</h2><div class="providers">${item.watch.map((provider) => `
    <a class="provider" href="${esc(provider.url || "#")}" data-external>
      ${provider.logo ? `<img src="${esc(provider.logo)}" alt="">` : ""}
      <div>${esc(provider.name)}<small>${esc(provider.offer)}</small></div>
    </a>`).join("")}</div><div class="hint" style="margin-top:6px;font-size:12px">Данные JustWatch через TMDB</div></div>`;
}

function entryHtml(item) {
  const entry = item.entry;
  const statuses = Object.entries(STATUS_LABELS).map(([status, label]) =>
    `<button class="status-btn ${entry?.status === status ? "active" : ""}" data-set-status="${status}">${label}</button>`).join("");
  let extra = "";
  if (entry) {
    const scores = Array.from({ length: 10 }, (_, index) => index + 1).map((score) =>
      `<button class="score-btn ${entry.score === score ? "active" : ""}" data-set-score="${score}">${score}</button>`).join("");
    const total = item.episodes ? ` / ${item.episodes}` : "";
    const progress = item.type !== "movie"
      ? `<div class="progress"><button data-progress="-1">−</button><span>Эпизод <b>${entry.progress || 0}</b>${total}</span><button data-progress="1">+</button></div>`
      : "";
    extra = `<div class="scores">${scores}</div>${progress}
      <button class="more" data-remove>Убрать из списка</button>`;
  }
  return `<div class="block"><h2>Мой список</h2><div class="statuses">${statuses}</div>${extra}</div>`;
}

async function renderMedia(key) {
  topbar.hidden = true;
  spinner();
  let item;
  try {
    item = await api(`/api/media/${encodeURIComponent(key)}`);
  } catch (error) {
    showError(error);
    return;
  }

  const draw = () => {
    view.innerHTML = `
      <div class="detail-head">
        ${posterHtml(item, false)}
        <div>
          <h1>${esc(item.title)}</h1>
          ${item.original_title && item.original_title !== item.title ? `<div class="original">${esc(item.original_title)}</div>` : ""}
          <div class="facts">${factsHtml(item)}</div>
        </div>
      </div>
      ${item.genres.length ? `<div class="genres">${item.genres.map((genre) => `<span class="genre">${esc(genre)}</span>`).join("")}</div>` : ""}
      ${entryHtml(item)}
      ${item.description ? `<div class="block"><h2>Описание</h2><div class="description collapsed">${esc(item.description)}</div><button class="more" data-expand>Показать полностью</button></div>` : ""}
      ${trailersHtml(item.trailers)}
      ${watchHtml(item)}
      <div class="block"><h2>Ссылки</h2><div class="links">${item.links.map((link) =>
        `<a href="${esc(link.url)}" data-external>${esc(link.name)}</a>`).join("")}</div></div>`;
    bindMedia();
  };

  const save = async (changes) => {
    const current = item.entry || {};
    const body = {
      title: item.title, poster: item.poster, year: item.year,
      status: current.status || "planned", score: current.score ?? null, progress: current.progress ?? null,
      ...changes,
    };
    try {
      item.entry = await api(`/api/list/${encodeURIComponent(key)}`, { method: "PUT", body: JSON.stringify(body) });
      haptic();
      draw();
    } catch (error) {
      toast(error.message);
    }
  };

  const bindMedia = () => {
    view.querySelectorAll("[data-set-status]").forEach((button) => button.addEventListener("click", () => {
      const status = button.dataset.setStatus;
      const changes = { status };
      if (status === "completed" && item.episodes) changes.progress = item.episodes;
      save(changes);
    }));
    view.querySelectorAll("[data-set-score]").forEach((button) => button.addEventListener("click", () => {
      const score = Number(button.dataset.setScore);
      save({ score: item.entry?.score === score ? null : score });
    }));
    view.querySelectorAll("[data-progress]").forEach((button) => button.addEventListener("click", () => {
      let progress = (item.entry?.progress || 0) + Number(button.dataset.progress);
      progress = Math.max(0, item.episodes ? Math.min(progress, item.episodes) : progress);
      const changes = { progress };
      if (item.episodes && progress === item.episodes) changes.status = "completed";
      else if (progress > 0 && item.entry?.status === "planned") changes.status = "watching";
      save(changes);
    }));
    view.querySelector("[data-remove]")?.addEventListener("click", async () => {
      try {
        await api(`/api/list/${encodeURIComponent(key)}`, { method: "DELETE" });
        item.entry = null;
        draw();
      } catch (error) {
        toast(error.message);
      }
    });
    view.querySelector("[data-expand]")?.addEventListener("click", (event) => {
      view.querySelector(".description").classList.remove("collapsed");
      event.target.remove();
    });
    view.querySelectorAll("[data-trailer]").forEach((button) => button.addEventListener("click", () => {
      view.querySelectorAll("[data-trailer]").forEach((other) => other.classList.toggle("active", other === button));
      view.querySelector(".trailer").src = `https://www.youtube-nocookie.com/embed/${button.dataset.trailer}`;
    }));
    view.querySelectorAll("a[data-external]").forEach((link) => link.addEventListener("click", (event) => {
      if (!tg) return;
      event.preventDefault();
      tg.openLink(link.href);
    }));
  };

  draw();
}

function navigate(hash, replace = false) {
  if (replace) history.replaceState(null, "", hash);
  else history.pushState(null, "", hash);
  route();
}

function setActiveTab(name) {
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.route === name));
}

function route() {
  const hash = location.hash || "#/";
  window.scrollTo(0, 0);
  if (hash.startsWith("#/media/")) {
    tg?.BackButton.show();
    renderMedia(decodeURIComponent(hash.slice("#/media/".length)));
    return;
  }
  tg?.BackButton.hide();
  if (hash === "#/list") {
    setActiveTab("list");
    renderList();
  } else if (hash === "#/random") {
    setActiveTab("random");
    renderRandom();
  } else {
    setActiveTab("home");
    renderHome();
  }
}

document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => {
  const target = { home: "#/", random: "#/random", list: "#/list" }[tab.dataset.route];
  if (tab.dataset.route === "random") navigate(target);
  else if (location.hash !== target) navigate(target);
}));

document.querySelectorAll("#type-chips .chip").forEach((chip) => chip.addEventListener("click", () => {
  state.type = chip.dataset.type;
  document.querySelectorAll("#type-chips .chip").forEach((other) => other.classList.toggle("active", other === chip));
  renderHome();
}));

let searchTimer;
searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.query = searchInput.value.trim();
    renderHome();
  }, 400);
});
searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  searchInput.blur();
  clearTimeout(searchTimer);
  state.query = searchInput.value.trim();
  renderHome();
});

tg?.BackButton.onClick(() => history.length > 1 ? history.back() : navigate("#/", true));
window.addEventListener("popstate", route);

api("/api/config").then((config) => {
  document.querySelectorAll("#type-chips .chip").forEach((chip) => {
    if (chip.dataset.type !== "all" && !config.sources.includes(chip.dataset.type)) chip.hidden = true;
  });
}).catch(() => {});

route();
