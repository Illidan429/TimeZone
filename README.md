# TimeZone

面向 B 站主播 **小时走神了** 的粉丝站与直播相关工具集合（灵感参考 [LAPLACE](https://laplace.live) / [laplace-live 组织](https://github.com/laplace-live) 的形态，本站为独立项目）。

- **计划域名**：`timezone.fan`（备案完成后接入）
- **代码仓库**：<https://github.com/Illidan429/TimeZone>

## 当前阶段

以 **功能与信息架构设计** 为主，见 [`docs/`](docs/)。后续再进入具体技术实现与部署（含阿里云 ECS）。**细进度**见 [规划与开发进度](docs/planning-and-progress.md)。

## 本仓库怎么用（协作）

| 角色 | 典型用法 |
|------|-----------|
| **站长（你）** | 打开 [`docs/`](docs/) 里的愿景、架构、[头脑风暴](docs/brainstorm-log.md)、[规划与进度](docs/planning-and-progress.md)，回忆讨论到哪、下一步要什么；在对话里把新需求告诉协作方。 |
| **主播（小时走神了）** | 偶尔浏览同一批文档或与站长沟通即可，不必跟代码细节。 |
| **协作开发（含 AI）** | 需求讨论优先记入 [brainstorm-log.md](docs/brainstorm-log.md)（按日期追加）；**里程碑、当前任务、进度** 记入 [planning-and-progress.md](docs/planning-and-progress.md)；定稿结论再合并进愿景 / 架构等主文档（见下节「文档维护约定」）。 |

## 文档索引

| 文档 | 说明 |
|------|------|
| [产品愿景与功能草案](docs/product-vision.md) | 首页气泡、录播表、歌切、小工具等 |
| [信息架构草案](docs/information-architecture.md) | 页面与模块划分（会随讨论更新） |
| [头脑风暴记录（按时间追加）](docs/brainstorm-log.md) | 需求讨论按日期追加，不整篇覆盖旧记录 |
| [规划与开发进度](docs/planning-and-progress.md) | 当前焦点、里程碑、按日期的进度更新 |
| [关联仓库与分支](docs/related-repositories.md) | 虚拟键盘 / Agent 等独立工程链接 |

## 前端骨架（第一期最小上线版）

- 目录：`web/`
- 入口页：`web/index.html`
- 子页：`web/pages/archive.html`、`web/pages/music.html`、`web/pages/tools.html`、`web/pages/news.html`
- 样式：`web/styles/base.css` + `web/styles/themes/default.css`
- 脚本：`web/scripts/main.js`

### 本地预览

唯一推荐方式（固定目录）：

```bash
python -m http.server 8000
```

然后访问：

- 首页：`http://localhost:8000/web/`
- 录播页：`http://localhost:8000/web/pages/archive.html`
- 录播数据：`http://localhost:8000/web/data/vod-events.json`

> 不支持 `file://` 直接双击打开页面（会导致录播 JSON 无法读取）。

### 录播数据（两段式）

1. **JSON 手动添加**：直接编辑 `web/data/vod-events.json`。  
2. **自动解析生成**：编辑 `web/data/vod-input.json`，然后执行：

```bash
python tools/build_vod_events.py
```

生成结果会写回 `web/data/vod-events.json`（录播页直接读取这个文件）。

### 录播页维护入口（轻量）

- **访客界面**不展示登录、口令或「管理」相关控件；普通打开 `.../archive.html` 只能浏览日历。
- **进入编辑**：在地址后加 `?manage=1` 访问同一页（例：`http://localhost:8000/web/pages/archive.html?manage=1`），按提示输入口令；成功后地址栏会自动去掉该参数，**当前标签页会话**内会出现「开启编辑」「导出 JSON」「退出管理」。
- 口令配置：`web/data/admin-config.json` 的 `archiveEditPasscode`。
- 仍为前端口令，仅防误操作；关闭标签页或点「退出管理」后需再次使用 `?manage=1`。

## 文档维护约定

**不需要**所有文档都做成「按日期一条条追加」。可以分成两类：

| 类型 | 适合哪些文档 | 怎么改 |
|------|----------------|--------|
| **按时间追加** | 头脑风暴、会议纪要、[规划与进度 · 更新记录](docs/planning-and-progress.md#更新记录)、变更日志（若以后有） | 每次在文末**新开一节日期**；旧节尽量不删，更正用「更正：」或附注。 |
| **整体或大块更新** | 产品愿景、信息架构、关联仓库说明、本 README、[规划与进度 · 里程碑/当前焦点](docs/planning-and-progress.md) | 共识清楚后**重写或合并段落**，让文档读起来是「当前真相」；不必保留历史版本在同一个文件里。 |

**衔接**：新想法、未定案讨论优先记在 [`docs/brainstorm-log.md`](docs/brainstorm-log.md)；**定稿或阶段性收敛**时，再把结论**写回**愿景 / 架构等主文档（可删掉过时段落，避免两处长期打架）。

## 与远程仓库同步

- **约定**：站长授权协作方在对话会话中 **视变更情况** 执行 `git commit` 与 `git push`，把本仓库与 GitHub 对齐。  
- **说明**：协作方 **无法**在无人发起对话时「按闹钟」自动同步；实际节奏是 **每次一起改完文档或代码后，尽量在同一会话里提交并推送**。推送需本机已配置 `origin` 与 GitHub 凭据（HTTPS/SSH）。
- **执行要求（长期）**：后续每次有效改动默认执行以下步骤：  
  1) 提交并推送 Git；2) 同步服务器到最新 `main`；3) 更新 `docs/planning-and-progress.md` 的更新记录。

## 可读性与结构清晰度原则（面向后续专家接手）

- **入口优先**：保持 `README` 作为总入口；新增重要文档时，先补 `README` 的「文档索引」。  
- **一文一责**：需求讨论写 `brainstorm-log`，阶段/任务写 `planning-and-progress`，长期结论回写 `product-vision` / `information-architecture`。  
- **命名直白**：文件名、标题、目录名优先使用可读中文语义（必要时附英文关键词），避免缩写堆叠。  
- **先结论后细节**：主文档优先给「当前真相」，历史过程放到按日期追加文档，避免让接手者在多份文档里拼图。  
- **改动留痕**：每次关键调整都在 `planning-and-progress` 的「更新记录」补一条，便于追踪决策背景。  
- **围绕两大优化目标组织内容**：后续结构与文档默认围绕 `UI好看` 与 `功能逻辑梳理` 两条主线，避免散点式记录。  
- **实现与文档双向可追踪**：页面/UI 变更要能在 IA 或进度文档找到对应模块；功能逻辑变更要能在愿景/架构里找到来源与去向。  

## 命名约定（品牌与称呼）

- **主播全称**：`小时走神了`
- **主播简称**：`小时`
- **站点英文品牌**：`TimeZone`
- **站点中文副标题 / 世界观称呼**：`小时的星球`（用于首页文案、活动视觉、宣传语）
- **使用建议**：正式介绍优先写「`小时走神了（小时）`」，站点名称使用「`TimeZone`」，需要强化人设氛围时配合「`小时的星球`」。

## 与「TimeZone-Virtual-Keyboard」的关系

虚拟键盘等 **OBS / 直播小工具** 在独立仓库开发；本仓库作为 **站点总仓**，将来在「工具」页通过链接或嵌入接入。

**进展记录**：[`feat/agent-packaging-and-oneclick-start`](https://github.com/jiaxuli960429-dotcom/TimeZone-Virtual-Keyboard/tree/feat/agent-packaging-and-oneclick-start) 分支（[TimeZone-Virtual-Keyboard](https://github.com/jiaxuli960429-dotcom/TimeZone-Virtual-Keyboard)）为当前主开发线，**进行中（约一半）**。详情见 [docs/related-repositories.md](docs/related-repositories.md)。

## 本地初始化（若从零克隆）

```bash
git clone https://github.com/Illidan429/TimeZone.git
cd TimeZone
```

若你已在本地创建本目录并需关联远程：

```bash
git remote add origin https://github.com/Illidan429/TimeZone.git
git branch -M main
git push -u origin main
```
