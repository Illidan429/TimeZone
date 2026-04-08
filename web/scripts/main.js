(function () {
  const page = document.body.dataset.page;
  if (!page) return;
  ensureGlobalTopbar(page);
  const titleMap = {
    home: "TimeZone | 小时的星球",
    archive: "录播表 | TimeZone",
    music: "听歌 | TimeZone",
    tools: "工具 | TimeZone",
    news: "公告 | TimeZone"
  };
  if (titleMap[page]) document.title = titleMap[page];

  if (page === "home") {
    initHomePage();
  }
  if (page === "archive") {
    initArchivePage();
  }
  if (page === "news") {
    initNewsPage();
  }
})();

const TZ_ARCHIVE_ADMIN_KEY = "tz_archive_admin";

function ensureGlobalTopbar(page) {
  let topbar = document.querySelector(".topbar");
  if (!topbar) {
    const isHome = page === "home";
    const base = isHome ? "" : "../";
    topbar = document.createElement("header");
    topbar.className = "topbar";
    topbar.innerHTML = `
      <a class="brand" href="${base}index.html">TimeZone</a>
      <nav class="nav">
        <a data-nav="archive" href="${base}pages/archive.html">录播表</a>
        <a data-nav="music" href="${base}pages/music.html">听歌</a>
        <a data-nav="tools" href="${base}pages/tools.html">工具</a>
        <a data-nav="news" href="${base}pages/news.html">公告</a>
      </nav>
    `;
    const first = document.body.firstChild;
    document.body.insertBefore(topbar, first);
  }

  const key = page === "home" ? null : page;
  if (key) {
    const active = topbar.querySelector(`.nav a[data-nav="${key}"]`);
    if (active) active.classList.add("active");
  }
}

async function initHomePage() {
  const statusDot = document.getElementById("live-status-dot");
  const statusText = document.getElementById("live-status-text");
  const roomLink = document.getElementById("live-status-link");
  if (!statusDot || !statusText || !roomLink) return;

  try {
    const resp = await fetch("/api/live/status", { cache: "no-store" });
    const data = await resp.json();
    if (!resp.ok || !data.ok) throw new Error(data.message || `HTTP ${resp.status}`);

    const isLive = Number(data.liveStatus) === 1;
    statusDot.classList.remove("online", "offline");
    statusDot.classList.add(isLive ? "online" : "offline");
    statusText.textContent = isLive ? "正在直播" : "当前未开播";
    if (data.roomUrl) roomLink.href = data.roomUrl;
  } catch (_err) {
    statusDot.classList.remove("online");
    statusDot.classList.add("offline");
    statusText.textContent = "状态获取失败";
  }
}

async function fetchJsonFromCandidates(paths) {
  let lastError = null;
  for (const p of paths) {
    try {
      const url = new URL(p, window.location.origin).toString();
      const resp = await fetch(url, { cache: "no-store" });
      if (!resp.ok) {
        lastError = new Error(`HTTP ${resp.status} for ${p}`);
        continue;
      }
      return await resp.json();
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError || new Error("fetch failed");
}

async function loadAdminConfig() {
  try {
    const cfgData = await fetchJsonFromCandidates(["/web/data/admin-config.json", "/data/admin-config.json"]);
    if (cfgData && typeof cfgData.archiveEditPasscode === "string") {
      return cfgData;
    }
  } catch (_err) {
    // ignore
  }
  return { archiveEditPasscode: "timezone-admin-please-change" };
}

/** 仅当 URL 含 ?manage=1 时弹出口令；成功后去掉参数。返回当前标签页是否具备维护会话。 */
function tryArchiveManageEntry(adminConfig) {
  const url = new URL(window.location.href);
  const wantsManage = url.searchParams.get("manage") === "1";
  const pass =
    (adminConfig && typeof adminConfig.archiveEditPasscode === "string" && adminConfig.archiveEditPasscode) ||
    "timezone-admin-please-change";
  if (wantsManage) {
    const hadSession = sessionStorage.getItem(TZ_ARCHIVE_ADMIN_KEY) === "1";
    if (!hadSession) {
      const input = window.prompt("请输入维护口令：");
      if (input && input === pass) {
        sessionStorage.setItem(TZ_ARCHIVE_ADMIN_KEY, "1");
      }
    }
    url.searchParams.delete("manage");
    const qs = url.searchParams.toString();
    const next = url.pathname + (qs ? `?${qs}` : "") + url.hash;
    window.history.replaceState(null, "", next);
  }
  return sessionStorage.getItem(TZ_ARCHIVE_ADMIN_KEY) === "1";
}

async function initArchivePage() {
  const statusEl = document.getElementById("calendar-status");
  let adminConfig = { archiveEditPasscode: "timezone-admin-please-change" };
  // 统一约定：仅支持在仓库根目录启动 http 服务后访问 /web/pages/archive.html。
  if (window.location.protocol === "file:") {
    if (statusEl) {
      statusEl.textContent = "不支持 file:// 直接打开。请在仓库根目录执行 `python -m http.server 8000`，然后访问 http://localhost:8000/web/pages/archive.html。";
      statusEl.classList.add("error-text");
    }
    setupArchiveCalendar([], adminConfig, { showAdminChrome: false });
    return;
  }

  try {
    adminConfig = await loadAdminConfig();

    const events = await fetchJsonFromCandidates(["/web/data/vod-events.json", "/data/vod-events.json"]);
    if (!Array.isArray(events)) throw new Error("Invalid data format");

    const showAdminChrome = tryArchiveManageEntry(adminConfig);
    if (statusEl) statusEl.textContent = "已从数据文件载入录播信息。";
    setupArchiveCalendar(Array.isArray(events) ? events : [], adminConfig, { showAdminChrome });
  } catch (err) {
    const showAdminChrome = tryArchiveManageEntry(adminConfig);
    if (statusEl) {
      statusEl.textContent = "录播数据读取失败。请检查 /web/data/vod-events.json 或 /data/vod-events.json 是否可访问；本地预览请在仓库根目录执行 `python -m http.server 8000`。";
      statusEl.classList.add("error-text");
    }
    setupArchiveCalendar([], adminConfig, { showAdminChrome });
  }
}

async function initNewsPage() {
  const listEl = document.getElementById("news-list");
  const statusEl = document.getElementById("news-status");
  const panelEl = document.getElementById("news-admin-panel");
  const tipEl = document.getElementById("news-admin-tip");
  const dateEl = document.getElementById("news-date");
  const titleEl = document.getElementById("news-title");
  const contentEl = document.getElementById("news-content");
  const addLocalBtn = document.getElementById("news-add-local");
  const saveBtn = document.getElementById("news-save-server");
  const logoutBtn = document.getElementById("news-admin-logout");
  if (!listEl || !statusEl || !panelEl || !dateEl || !titleEl || !contentEl || !addLocalBtn || !saveBtn || !logoutBtn) return;

  const adminConfig = await loadAdminConfig();
  const isAdmin = tryArchiveManageEntry(adminConfig);
  if (isAdmin) {
    panelEl.classList.remove("hidden");
    if (tipEl) tipEl.classList.remove("hidden");
  }

  let posts = [];
  try {
    const data = await fetchJsonFromCandidates(["/web/data/news-posts.json", "/data/news-posts.json"]);
    posts = Array.isArray(data) ? data : [];
    statusEl.textContent = "开发日记已载入。";
  } catch (_err) {
    statusEl.textContent = "开发日记读取失败。";
    statusEl.classList.add("error-text");
  }

  function renderPosts() {
    if (!posts.length) {
      listEl.innerHTML = '<div class="news-item"><div class="news-item-content">暂无内容。</div></div>';
      return;
    }
    const sorted = [...posts].sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
    listEl.innerHTML = sorted
      .map(
        (p) => `
        <article class="news-item">
          <div class="news-item-title">${(p.title || "").replace(/</g, "&lt;")}</div>
          <div class="news-item-meta">${(p.date || "").replace(/</g, "&lt;")}</div>
          <div class="news-item-content">${(p.content || "").replace(/</g, "&lt;")}</div>
        </article>
      `
      )
      .join("");
  }

  renderPosts();
  if (!isAdmin) return;

  dateEl.value = new Date().toISOString().slice(0, 10);
  addLocalBtn.addEventListener("click", () => {
    const date = (dateEl.value || "").trim();
    const title = (titleEl.value || "").trim();
    const content = (contentEl.value || "").trim();
    if (!date || !title || !content) {
      statusEl.textContent = "请先填写日期、标题和内容。";
      statusEl.classList.add("error-text");
      return;
    }
    statusEl.classList.remove("error-text");
    posts.push({ date, title, content });
    renderPosts();
    statusEl.textContent = "已加入列表预览，记得点“保存到服务器”。";
    titleEl.value = "";
    contentEl.value = "";
  });

  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    const old = saveBtn.textContent;
    saveBtn.textContent = "保存中...";
    try {
      const resp = await fetch("/api/admin/news-posts", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Admin-Passcode": adminConfig.archiveEditPasscode || "timezone-admin-please-change"
        },
        body: JSON.stringify({ posts })
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data.ok) throw new Error(data.message || `HTTP ${resp.status}`);
      statusEl.classList.remove("error-text");
      statusEl.textContent = "开发日记已保存到服务器。";
    } catch (err) {
      statusEl.classList.add("error-text");
      statusEl.textContent = `保存失败：${err.message || "未知错误"}`;
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = old;
    }
  });

  logoutBtn.addEventListener("click", () => {
    sessionStorage.removeItem(TZ_ARCHIVE_ADMIN_KEY);
    window.location.reload();
  });
}

function setupArchiveCalendar(events, adminConfig, options = {}) {
  const showAdminChrome = Boolean(options.showAdminChrome);
  const calendarEl = document.getElementById("vod-calendar");
  const titleEl = document.getElementById("calendar-title");
  const prevBtn = document.getElementById("calendar-prev");
  const nextBtn = document.getElementById("calendar-next");
  const toolbarRight = document.getElementById("calendar-toolbar-admin");
  if (!calendarEl || !titleEl || !prevBtn || !nextBtn || !toolbarRight) return;

  toolbarRight.innerHTML = "";
  let editToggleBtn = null;
  let exportBtn = null;
  let logoutBtn = null;
  let refreshBtn = null;
  if (showAdminChrome) {
    function mkBtn(id, label) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "calendar-btn";
      b.id = id;
      b.textContent = label;
      return b;
    }
    editToggleBtn = mkBtn("calendar-edit-toggle", "开启编辑");
    refreshBtn = mkBtn("calendar-refresh-vod", "抓取最新录播");
    exportBtn = mkBtn("calendar-export", "导出 JSON");
    logoutBtn = mkBtn("calendar-admin-logout", "退出管理");
    toolbarRight.append(editToggleBtn, refreshBtn, exportBtn, logoutBtn);
    const adminHints = document.getElementById("archive-admin-hints");
    if (adminHints) adminHints.classList.remove("hidden");
  }

  let editMode = false;
  const isAdmin = showAdminChrome;
  const sourceEvents = Array.isArray(events) ? [...events] : [];
  const sortedDates = sourceEvents
    .map((item) => item.date)
    .filter(Boolean)
    .sort();
  const minDate = sortedDates.length ? new Date(`${sortedDates[0]}T00:00:00`) : null;
  const maxDate = sortedDates.length ? new Date(`${sortedDates[sortedDates.length - 1]}T00:00:00`) : null;

  function buildByDate() {
    const byDate = new Map();
    sourceEvents.forEach((item) => {
      if (!byDate.has(item.date)) byDate.set(item.date, []);
      byDate.get(item.date).push(item);
    });
    return byDate;
  }

  const today = new Date();
  let viewYear = today.getFullYear();
  let viewMonth = today.getMonth();

  function render() {
    const byDate = buildByDate();
    const firstDay = new Date(viewYear, viewMonth, 1);
    const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
    const startWeekday = firstDay.getDay();
    const cells = [];

    titleEl.textContent = `${viewYear}年${String(viewMonth + 1).padStart(2, "0")}月`;
    const currentMonthStart = new Date(viewYear, viewMonth, 1);
    if (minDate) {
      const minMonthStart = new Date(minDate.getFullYear(), minDate.getMonth(), 1);
      prevBtn.disabled = currentMonthStart <= minMonthStart;
    } else {
      prevBtn.disabled = true;
    }
    if (maxDate) {
      const maxMonthStart = new Date(maxDate.getFullYear(), maxDate.getMonth(), 1);
      nextBtn.disabled = currentMonthStart >= maxMonthStart;
    } else {
      nextBtn.disabled = true;
    }

    for (let i = 0; i < startWeekday; i += 1) {
      cells.push('<div class="cal-cell cal-empty"></div>');
    }

    for (let day = 1; day <= daysInMonth; day += 1) {
      const dateKey = `${viewYear}-${String(viewMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
      const list = byDate.get(dateKey) || [];
      const itemsHtml = list
        .map((item, idx) => `<a class="vod-item ${editMode ? "editable" : ""}" data-date="${dateKey}" data-idx="${idx}" href="${item.url}" target="_blank" rel="noopener noreferrer">${item.title}</a>`)
        .join("");

      cells.push(`
        <div class="cal-cell ${editMode ? "editable" : ""}" data-date="${dateKey}">
          <div class="cal-day">${day}</div>
          <div class="cal-items">${itemsHtml || '<span class="cal-none">-</span>'}</div>
        </div>
      `);
    }

    calendarEl.innerHTML = cells.join("");
  }

  function upsertEvent(date, indexInDay, next) {
    const indices = [];
    sourceEvents.forEach((e, i) => {
      if (e.date === date) indices.push(i);
    });
    const targetIndex = indices[indexInDay];
    if (typeof targetIndex === "number") {
      sourceEvents[targetIndex] = { ...sourceEvents[targetIndex], ...next };
    } else {
      sourceEvents.push({ date, ...next });
    }
  }

  calendarEl.addEventListener("dblclick", (ev) => {
    if (!isAdmin || !editMode) return;
    const itemEl = ev.target.closest(".vod-item");
    if (itemEl) {
      ev.preventDefault();
      const date = itemEl.dataset.date;
      const idx = Number(itemEl.dataset.idx || "0");
      const oldTitle = itemEl.textContent || "";
      const oldUrl = itemEl.getAttribute("href") || "";
      const nextTitle = window.prompt("修改标题：", oldTitle);
      if (!nextTitle) return;
      const nextUrl = window.prompt("修改链接：", oldUrl);
      if (!nextUrl) return;
      upsertEvent(date, idx, { title: nextTitle.trim(), url: nextUrl.trim() });
      render();
      return;
    }

    const cellEl = ev.target.closest(".cal-cell[data-date]");
    if (!cellEl) return;
    const date = cellEl.dataset.date;
    const addTitle = window.prompt(`为 ${date} 新增条目，输入标题：`);
    if (!addTitle) return;
    const addUrl = window.prompt("输入链接：", "https://www.bilibili.com/video/");
    if (!addUrl) return;
    upsertEvent(date, Number.MAX_SAFE_INTEGER, { title: addTitle.trim(), url: addUrl.trim() });
    render();
  });

  prevBtn.addEventListener("click", () => {
    if (prevBtn.disabled) return;
    viewMonth -= 1;
    if (viewMonth < 0) {
      viewMonth = 11;
      viewYear -= 1;
    }
    render();
  });

  nextBtn.addEventListener("click", () => {
    if (nextBtn.disabled) return;
    viewMonth += 1;
    if (viewMonth > 11) {
      viewMonth = 0;
      viewYear += 1;
    }
    render();
  });

  if (editToggleBtn) {
    editToggleBtn.addEventListener("click", () => {
      if (!isAdmin) return;
      editMode = !editMode;
      editToggleBtn.textContent = editMode ? "关闭编辑" : "开启编辑";
      render();
    });
  }

  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      if (!isAdmin) return;
      const clean = sourceEvents
        .filter((item) => item.date && item.title && item.url)
        .sort((a, b) => a.date.localeCompare(b.date));
      const blob = new Blob([`${JSON.stringify(clean, null, 2)}\n`], { type: "application/json;charset=utf-8" });
      const href = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = href;
      a.download = "vod-events.json";
      a.click();
      URL.revokeObjectURL(href);
    });
  }

  if (refreshBtn) {
    const statusEl = document.getElementById("calendar-status");
    refreshBtn.addEventListener("click", async () => {
      if (!isAdmin) return;
      refreshBtn.disabled = true;
      const oldText = refreshBtn.textContent;
      refreshBtn.textContent = "抓取中...";
      if (statusEl) {
        statusEl.classList.remove("error-text");
        statusEl.textContent = "正在服务器抓取最新录播，请稍候...";
      }
      try {
        const resp = await fetch("/api/admin/refresh-vod", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Admin-Passcode":
              (adminConfig && typeof adminConfig.archiveEditPasscode === "string" && adminConfig.archiveEditPasscode) ||
              "timezone-admin-please-change"
          },
          body: "{}"
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || !data.ok) {
          throw new Error((data && data.message) || `HTTP ${resp.status}`);
        }
        if (statusEl) {
          statusEl.classList.remove("error-text");
          statusEl.textContent = "录播抓取完成，正在刷新页面数据...";
        }
        window.location.reload();
      } catch (err) {
        if (statusEl) {
          statusEl.classList.add("error-text");
          statusEl.textContent = `抓取失败：${err.message || "未知错误"}`;
        }
      } finally {
        refreshBtn.disabled = false;
        refreshBtn.textContent = oldText;
      }
    });
  }

  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      sessionStorage.removeItem(TZ_ARCHIVE_ADMIN_KEY);
      window.location.reload();
    });
  }

  render();
}
