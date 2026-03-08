# IG Chrome Extension 可行性验证报告

## 1. 验证目标

确认 Instagram 网页端（已登录状态下）是否通过任何 API 或前端数据暴露 **following 列表的真实关注时间**，以评估"纯网页侧 Chrome 扩展 + 按时间排序"方案的可行性。

---

## 2. 调研范围

| 接口类型 | 端点 | 调查状态 |
|----------|------|----------|
| Web GraphQL API | `www.instagram.com/graphql/query/?query_hash=d04b0a864b4b54837c0d870b0e77e076` | 已验证 |
| Mobile/Private REST API | `i.instagram.com/api/v1/friendships/{user_id}/following/` | 已验证 |
| 官方 Graph API (Meta for Developers) | `graph.instagram.com` | 已验证 |
| 开源项目 & Chrome Web Store 扩展 | dilame/instagram-private-api, stabby17/Instagram-Follower-Export-Tool, InsFo, Export IG 等 | 已验证 |

---

## 3. 核心发现

### 3.1 Web GraphQL 端点 — 无时间字段

Instagram 网页端的 following 列表通过 GraphQL 获取，响应结构为：

```
data.user.edge_follow.edges[].node
```

**node 包含的字段**：
- `id`, `username`, `full_name`, `profile_pic_url`
- `is_private`, `is_verified`
- `followed_by_viewer`, `follows_viewer`

**不包含**：任何时间戳字段（无 `followed_at`、`created_at`、`date_followed` 或等价字段）。

**无排序参数**：GraphQL 查询变量仅支持 `id`, `first`, `after`, `include_reel`, `fetch_mutual`，不支持按时间排序。

### 3.2 Mobile/Private REST 端点 — 有排序但无时间值

`i.instagram.com/api/v1/friendships/{user_id}/following/` 端点：

**支持 `order` 参数**：
- `order=date_followed_latest`（最近关注在前）
- `order=date_followed_earliest`（最早关注在前）

**限制**：
- 仅对自己的账户可靠生效，查询他人 following 时排序不稳定
- 响应中的 user 对象仍然 **不包含时间戳字段**
- 只是改变了返回结果的 **顺序**，不暴露具体 **日期值**

**响应结构**：
```json
{
  "users": [
    {"pk": "...", "username": "...", "full_name": "...", "profile_pic_url": "...", "is_private": false, ...}
  ],
  "big_list": true,
  "page_size": 200,
  "next_max_id": "...",
  "status": "ok"
}
```

**关键认知**：这正是 Instagram 手机端 "Sort By → Date Followed" 功能的底层实现。手机端自身也不显示具体日期，只是改变列表顺序。

### 3.3 Chrome 扩展可以调用 Mobile API

在已登录 `www.instagram.com` 的浏览器中：
- `i.instagram.com` 共享相同的 session cookies（`sessionid`, `csrftoken`, `ds_user_id`）
- Chrome 扩展通过 `host_permissions` 声明 `*://*.instagram.com/*` 后，可在 background/service worker 中用 `fetch()` 直接调用 mobile API
- 多个现有 Chrome Web Store 扩展（InsFo、Export IG Followers-Following）已验证此路径可行

### 3.4 Instagram 导出包 — 唯一可靠的精确时间源

当前项目依赖的 Instagram 官方导出 JSON 是 **唯一包含精确 Unix timestamp** 的数据源：

```json
{
  "title": "username",
  "string_list_data": [{"href": "https://www.instagram.com/_u/username", "timestamp": 1772916491}]
}
```

没有任何网页 API 提供等价精度的时间数据。

---

## 4. 结论：条件性 GO

### 判定标准回顾

| 标准 | 结果 |
|------|------|
| 网页接口能稳定拿到每个 following 的精确关注时间戳 | **不通过** — 无任何 API 返回时间值 |
| 网页接口能按关注时间排序 following 列表 | **通过** — mobile API 的 `order=date_followed_latest` 可用 |
| Chrome 扩展能在已登录状态下调用相关 API | **通过** — cookie 共享 + host_permissions 可行 |

### 为什么仍然建议 GO

你的原始需求是：

> "IG的手机端是可以实现 following 按时间排序，但网页端被限制，
> 我希望能有某种方式，很方便的网页端也可以查看筛选"

这本质上是 **把手机端的 "按关注时间排序" 能力搬到网页端**。

事实：Instagram 手机端自身也不显示具体关注日期，只是将列表按时间重新排序。Chrome 扩展通过 mobile API 的 `order=date_followed_latest` 参数可以完全复现这一行为。

因此：
- **如果你的目标是"网页端也能像手机一样按关注时间排序查看 following"** → **GO，完全可行**
- **如果你的目标是"看到每个 following 的具体关注日期（如 2024-03-15）"** → **需要额外结合导出包数据**

### 推荐路线

**主路线（纯网页侧）**：
Chrome 扩展在 popup 中展示 following 列表，通过 mobile API + `order=date_followed_latest` 获取按时间排序的结果，支持搜索和筛选。

**增强路线（可选）**：
允许用户在扩展中导入 IG 导出 JSON，用于补充精确时间戳和互动数据。这样每个 following 旁边可以显示具体关注日期。

---

## 5. 风险清单

| 风险 | 严重度 | 缓解措施 |
|------|--------|----------|
| IG 更改/废弃 mobile API 端点或 `order` 参数 | 高 | 扩展中做版本检测，fallback 到 GraphQL 默认顺序 |
| 大量 following (1000+) 时分页请求可能触发限流 | 中 | 增量加载 + 缓存 + 合理延迟 |
| `i.instagram.com` 的 CORS 策略可能阻止 content script 直接调用 | 低 | 通过 background service worker 发请求（不受 CORS 限制） |
| session cookie 过期或被轮换 | 低 | 扩展在请求失败时提示用户刷新 IG 页面重新登录 |
| Chrome Web Store 审核对 IG API 调用的合规性要求 | 中 | 仅限个人使用 / 不上架 / 或符合 CWS 最小权限策略 |

---

## 6. 技术架构概要

```
┌──────────────────────────────────────────────────────────┐
│                    Chrome Extension                       │
│                                                          │
│  ┌─────────┐   ┌───────────────┐   ┌──────────────────┐ │
│  │  Popup   │◄──│  Background   │──►│ i.instagram.com  │ │
│  │  (UI)    │   │  Service      │   │ /api/v1/         │ │
│  │          │   │  Worker       │   │ friendships/     │ │
│  │ - 列表   │   │               │   │ {uid}/following/ │ │
│  │ - 搜索   │   │ - API 调用    │   │ ?order=date_     │ │
│  │ - 筛选   │   │ - 缓存管理    │   │  followed_latest │ │
│  │ - 排序   │   │ - 分页拼接    │   └──────────────────┘ │
│  └─────────┘   └───────────────┘                         │
│                       │                                  │
│                       ▼                                  │
│              ┌──────────────────┐                        │
│              │  chrome.storage  │                        │
│              │  (缓存 + 设置)   │                        │
│              └──────────────────┘                        │
└──────────────────────────────────────────────────────────┘
```

---

## 7. 现有仓库模块迁移评估

| 现有模块 | 可复用程度 | 迁移方式 |
|----------|-----------|----------|
| `core/models.py` FollowRecord 数据模型 | 高 | 直接翻译为 TypeScript interface |
| `core/services/filter_service.py` 筛选逻辑 | 高 | 翻译为 TS 纯函数 |
| `core/services/similarity_service.py` 相似度排序 | 中 | 可迁移，但第一期可不做 |
| `core/classify/region_classifier.py` 地区推断 | 中 | 关键词规则可复用，需要 bio 数据 |
| `core/importers/instagram_export.py` 导出包解析 | 低（主路线）/ 高（增强路线） | 仅增强路线需要 |
| `core/storage/sqlite_repo.py` SQLite 存储 | 不可复用 | 改为 chrome.storage.local 或 IndexedDB |
| `app/main.py` Streamlit UI | 不可复用 | 完全重写为 popup HTML/CSS/JS |
| `core/services/avatar_service.py` 头像抓取 | 不需要 | mobile API 响应已含 profile_pic_url |
| `core/services/profile_metadata_service.py` 资料抓取 | 不需要 | mobile API 响应已含基本信息 |

---

## 8. 建议的 MVP 范围

**Phase 1（核心 MVP）**：
1. manifest.json + background service worker + popup
2. 从 cookie 获取 session + user_id
3. 调用 `i.instagram.com/api/v1/friendships/{uid}/following/?order=date_followed_latest`
4. 分页拼接完整 following 列表
5. popup 中展示可滚动列表（头像 + 用户名 + 序号）
6. 文本搜索过滤
7. 点击跳转到 IG 个人主页

**Phase 2（增强）**：
- 导入 IG 导出 JSON 补充精确时间戳
- 地区/关键词筛选
- 互动数据整合
- 列表缓存与增量更新
