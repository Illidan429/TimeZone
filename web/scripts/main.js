(function () {
  const page = document.body.dataset.page;
  if (!page) return;
  const titleMap = {
    home: "TimeZone | 小时的星球",
    archive: "录播表 | TimeZone",
    music: "听歌 | TimeZone",
    tools: "工具 | TimeZone",
    news: "公告 | TimeZone"
  };
  if (titleMap[page]) document.title = titleMap[page];

  if (page === "archive") {
    initArchivePage();
  }
})();

async function initArchivePage() {
  const statusEl = document.getElementById("calendar-status");
  // 统一约定：仅支持在仓库根目录启动 http 服务后访问 /web/pages/archive.html。
  if (window.location.protocol === "file:") {
    if (statusEl) {
      statusEl.textContent = "不支持 file:// 直接打开。请在仓库根目录执行 `python -m http.server 8000`，然后访问 http://localhost:8000/web/pages/archive.html。";
      statusEl.classList.add("error-text");
    }
    setupArchiveCalendar([]);
    return;
  }

  try {
    const dataUrl = new URL("/web/data/vod-events.json", window.location.origin).toString();
    const resp = await fetch(dataUrl, { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const events = await resp.json();
    if (!Array.isArray(events)) throw new Error("Invalid data format");

    if (statusEl) statusEl.textContent = "已从数据文件载入录播信息。";
    setupArchiveCalendar(Array.isArray(events) ? events : []);
  } catch (err) {
    if (statusEl) {
      statusEl.textContent = "录播数据读取失败。请固定使用仓库根目录服务：`python -m http.server 8000`，并检查 http://localhost:8000/web/data/vod-events.json 是否可访问。";
      statusEl.classList.add("error-text");
    }
    setupArchiveCalendar([]);
  }
}

function setupArchiveCalendar(events) {
  const calendarEl = document.getElementById("vod-calendar");
  const titleEl = document.getElementById("calendar-title");
  const prevBtn = document.getElementById("calendar-prev");
  const nextBtn = document.getElementById("calendar-next");
  const editToggleBtn = document.getElementById("calendar-edit-toggle");
  const exportBtn = document.getElementById("calendar-export");
  if (!calendarEl || !titleEl || !prevBtn || !nextBtn || !editToggleBtn || !exportBtn) return;

  let editMode = false;
  const sourceEvents = Array.isArray(events) ? [...events] : [];

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
    if (!editMode) return;
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
    viewMonth -= 1;
    if (viewMonth < 0) {
      viewMonth = 11;
      viewYear -= 1;
    }
    render();
  });

  nextBtn.addEventListener("click", () => {
    viewMonth += 1;
    if (viewMonth > 11) {
      viewMonth = 0;
      viewYear += 1;
    }
    render();
  });

  editToggleBtn.addEventListener("click", () => {
    editMode = !editMode;
    editToggleBtn.textContent = editMode ? "关闭编辑" : "开启编辑";
    render();
  });

  exportBtn.addEventListener("click", () => {
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

  render();
}
