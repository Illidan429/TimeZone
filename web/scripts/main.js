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
  const fallbackEvents = [
    { date: "2026-04-02", title: "直播回放：四月开场", url: "https://www.bilibili.com" },
    { date: "2026-04-06", title: "直播回放：聊天局", url: "https://www.bilibili.com" }
  ];
  try {
    const dataUrl = new URL("../data/vod-events.json", window.location.href).toString();
    const resp = await fetch(dataUrl, { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const events = await resp.json();
    if (statusEl) statusEl.textContent = "已从数据文件载入录播信息。";
    setupArchiveCalendar(Array.isArray(events) ? events : []);
  } catch (err) {
    if (statusEl) {
      statusEl.textContent = "录播数据读取失败，已使用内置示例数据。请用 `python -m http.server 8000` 方式预览并检查 web/data/vod-events.json。";
      statusEl.classList.add("error-text");
    }
    setupArchiveCalendar(fallbackEvents);
  }
}

function setupArchiveCalendar(events) {
  const calendarEl = document.getElementById("vod-calendar");
  const titleEl = document.getElementById("calendar-title");
  const prevBtn = document.getElementById("calendar-prev");
  const nextBtn = document.getElementById("calendar-next");
  if (!calendarEl || !titleEl || !prevBtn || !nextBtn) return;

  const byDate = new Map();
  events.forEach((item) => {
    if (!byDate.has(item.date)) byDate.set(item.date, []);
    byDate.get(item.date).push(item);
  });

  const today = new Date();
  let viewYear = today.getFullYear();
  let viewMonth = today.getMonth();

  function render() {
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
        .map((item) => `<a class="vod-item" href="${item.url}" target="_blank" rel="noopener noreferrer">${item.title}</a>`)
        .join("");

      cells.push(`
        <div class="cal-cell">
          <div class="cal-day">${day}</div>
          <div class="cal-items">${itemsHtml || '<span class="cal-none">-</span>'}</div>
        </div>
      `);
    }

    calendarEl.innerHTML = cells.join("");
  }

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

  render();
}
