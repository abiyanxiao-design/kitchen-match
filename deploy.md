# 部署到 Vercel + Supabase

这版已经不再依赖 SQLite 和本地图片存储，目标是：

- 数据库存到 `Supabase Postgres`
- 图片存到 `Supabase Storage`
- 前后端部署到 `Vercel 免费版`

## 0. 你会用到的文件

- 表结构：
  [supabase/schema.sql](/Users/mac/Documents/Codex/2026-06-04/rough/supabase/schema.sql)
- Storage bucket：
  [supabase/storage.sql](/Users/mac/Documents/Codex/2026-06-04/rough/supabase/storage.sql)
- 环境变量模板：
  [.env.example](/Users/mac/Documents/Codex/2026-06-04/rough/.env.example)
- Vercel 配置：
  [vercel.json](/Users/mac/Documents/Codex/2026-06-04/rough/vercel.json)

## 1. 创建 Supabase 项目

1. 打开 [Supabase](https://supabase.com/)。
2. 新建一个项目。
3. 记下项目的 `Project URL`。
4. 在 `Settings -> API` 里拿到：
   - `Project URL`
   - `service_role` key
5. 在 `Connect` 面板里复制 `Transaction pooler` 连接串。

给这个项目用的连接串，建议直接用 `Transaction pooler` 的 `6543` 端口，因为 Supabase 官方文档把它定位为适合 serverless / edge 场景，而 Vercel 的 Python Function 正是这种短连接场景。来源：
[Supabase: Connect to your database](https://supabase.com/docs/guides/database/connecting-to-postgres)

## 2. 在 Supabase 里建表

1. 打开 `SQL Editor`。
2. 复制 [supabase/schema.sql](/Users/mac/Documents/Codex/2026-06-04/rough/supabase/schema.sql) 的内容。
3. 执行。

这会创建：

- `users`
- `app_sessions`
- `posts`

## 3. 创建 Storage bucket

1. 还是在 `SQL Editor` 里。
2. 复制 [supabase/storage.sql](/Users/mac/Documents/Codex/2026-06-04/rough/supabase/storage.sql) 的内容。
3. 执行。

默认会创建一个公开 bucket：

- `post-images`

Supabase 官方文档说明，公开 bucket 可以直接通过公共 URL 读取文件；上传、删除等操作仍受权限控制。这里我们的上传走服务端 `service_role`，所以不需要前端直连 Supabase。来源：
[Supabase: Storage Buckets](https://supabase.com/docs/guides/storage/buckets/fundamentals)
[Supabase: Creating Buckets](https://supabase.com/docs/guides/storage/buckets/creating-buckets)

## 4. 本地先跑通

在项目目录：

```bash
cd /Users/mac/Documents/Codex/2026-06-04/rough
cp .env.example .env
```

把 `.env` 填成你自己的值，然后执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
set -a
source .env
set +a
python3 server.py
```

打开：

[http://127.0.0.1:8787](http://127.0.0.1:8787)

本地先验证这几件事：

1. 注册新账号
2. 登录
3. 发一道菜
4. 上传照片
5. 看“今天撞菜”
6. 看“我的记录”

## 5. 推到 GitHub

如果还没提交：

```bash
git add .
git commit -m "Migrate kitchen-match to Supabase and Vercel"
```

然后新建 GitHub 仓库并推上去：

```bash
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_NAME/kitchen-match.git
git push -u origin main
```

## 6. 在 Vercel 创建项目

1. 打开 [Vercel](https://vercel.com/)。
2. 选择 `Add New...` -> `Project`。
3. 导入你的 GitHub 仓库。
4. Framework 可以保持自动检测或选 `Other`。
5. 不需要自定义构建命令。

这个项目用的是 `api/index.py` 作为 Vercel Python Function，同时保留 `index.html`、`styles.css`、`app.js` 为静态资源。Vercel 官方 Flask 文档说明 Flask 应用会作为单个 Vercel Function 运行；Vercel `vercel.json` 文档也支持把 HTML 作为静态文件、Python 作为函数一起部署。来源：
[Vercel: Flask on Vercel](https://vercel.com/docs/frameworks/backend/flask/)
[Vercel: vercel.json](https://vercel.com/docs/project-configuration/vercel-json)

## 7. 在 Vercel 配环境变量

把下面这些环境变量都加进去：

- `SUPABASE_DB_URL`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_STORAGE_BUCKET`

值示例见：

[.env.example](/Users/mac/Documents/Codex/2026-06-04/rough/.env.example)

说明：

- `SUPABASE_DB_URL`
  用 Supabase `Transaction pooler` 连接串，建议保留 `?sslmode=require`
- `SUPABASE_URL`
  形如 `https://PROJECT_REF.supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY`
  从 `Settings -> API` 复制
- `SUPABASE_STORAGE_BUCKET`
  默认填 `post-images`

`KITCHEN_HOST` 和 `KITCHEN_PORT` 不需要在 Vercel 上配置，它们只用于本地运行。

## 8. 触发第一次部署

环境变量填好后，点 `Deploy`。

部署完成后，Vercel 会给你一个公开地址，例如：

- `https://kitchen-match.vercel.app`

## 9. 上线后验收

用公网地址做一遍完整验证：

1. 注册一个新账号
2. 登录
3. 发一道菜
4. 上传一张照片
5. 刷新页面，确认记录还在
6. 退出再登录，确认会话还在工作

## 10. 可以发给家人朋友用了

确认没问题之后，把 Vercel 给你的链接直接发给别人即可。
