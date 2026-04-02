(function () {
  const page = document.body.dataset.page;
  if (!page) return;
  const titleMap = {
    home: "TimeZone | 小时走神了",
    archive: "录播表 | TimeZone",
    music: "听歌 | TimeZone",
    tools: "工具 | TimeZone",
    news: "公告 | TimeZone"
  };
  if (titleMap[page]) document.title = titleMap[page];
})();
