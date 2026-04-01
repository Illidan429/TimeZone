# TimeZone

面向 B 站主播 **小时走神了** 的粉丝站与直播相关工具集合（灵感参考 [LAPLACE](https://laplace.live) / [laplace-live 组织](https://github.com/laplace-live) 的形态，本站为独立项目）。

- **计划域名**：`timezone.fan`（备案完成后接入）
- **代码仓库**：<https://github.com/Illidan429/TimeZone>

## 当前阶段

以 **功能与信息架构设计** 为主，见 [`docs/`](docs/)。后续再进入具体技术实现与部署（含阿里云 ECS）。

## 文档索引

| 文档 | 说明 |
|------|------|
| [产品愿景与功能草案](docs/product-vision.md) | 首页气泡、录播表、歌切、小工具等 |
| [信息架构草案](docs/information-architecture.md) | 页面与模块划分（会随讨论更新） |

## 与「TimeZone-Virtual-Keyboard」的关系

虚拟键盘等 **OBS / 直播小工具** 可单独维护仓库；本仓库作为 **站点总仓**，通过链接或后续嵌入方式接入工具页（具体实现待定）。

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
