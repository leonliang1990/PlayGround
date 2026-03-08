# Git 关键词说明（极简版）

目标：单人、低心智负担。只记 3 个关键词即可。

## 关键词

- `迭代` / `iterate`
- `发版` / `publish`
- `回滚` / `rollback`

## 关键词行为

### 1) 迭代 / iterate

表示：完成一轮代码改动后，先做本地快照（小一级命令）。

默认动作：
1. `git add -A`
2. `git commit`
3. 默认不 push，不改版本号，不打 tag

### 2) 发版 / publish

表示：把当前“已验证成功”的版本发布到 GitHub（大一级命令）。

默认动作：
1. 扩展版本号做 patch 升级（`x.y.z -> x.y.(z+1)`）
2. `git add -A`
3. `git commit`
4. `git push`
5. `git tag v<version>` 并 `git push origin v<version>`

版本号文件优先：
- `extension/manifest.json`
- 若不存在则 `ig-following-sort/extension/manifest.json`

### 3) 回滚 / rollback

表示：当前版本有问题，恢复到上一个稳定版本。

默认动作：
1. 未指定版本号时，回滚到“上一个 tag”
2. 指定版本号时（如 `rollback v0.3.0`），回滚到指定 tag
3. 默认只本地回滚，不 push
4. 只有你明确说“回滚并同步”，才会 push 到 GitHub

## Git 概念速查（1 分钟）

- `工作区`：你正在改的文件
- `commit`：本地保存一个“代码快照”
- `push`：把本地 commit 上传到 GitHub（上传的是代码改动，不是新建平行项目）
- `tag`：给某个 commit 打版本锚点（如 `v0.3.0`）
- `rollback`：把代码恢复到旧版本（通常回到某个 tag）

## 安全规则

- 不提交隐私数据：`IG_INFO/`、`.env`、密钥类文件
- 若发现疑似敏感文件，会先提示确认
