# 今日厨房

一个 mobile-first 的厨房撞菜小产品，现已迁移到 `Supabase Postgres + Supabase Storage`，部署目标改为 `Vercel 免费版`。

现在它支持：

- 注册和登录
- 发一道菜
- 可选上传一张照片并预览
- 今日撞菜结果
- 我的长期记录

## 技术栈

- 前端：原有静态 UI，不改界面
- API：Flask
- 数据库：Supabase Postgres
- 图片：Supabase Storage
- 部署：Vercel

## 本地启动

1. 复制环境变量模板：

```bash
cp .env.example .env
```

2. 在 `.env` 里填入你的 Supabase 信息。

3. 安装依赖并启动：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
set -a
source .env
set +a
python3 server.py
```

4. 打开：

[http://127.0.0.1:8787](http://127.0.0.1:8787)

## Supabase 需要创建的内容

- 表结构 SQL：
  [supabase/schema.sql](/Users/mac/Documents/Codex/2026-06-04/rough/supabase/schema.sql)
- Storage bucket SQL：
  [supabase/storage.sql](/Users/mac/Documents/Codex/2026-06-04/rough/supabase/storage.sql)
- 环境变量模板：
  [.env.example](/Users/mac/Documents/Codex/2026-06-04/rough/.env.example)

## 测试账号

当数据库里还没有任何用户时，应用第一次启动会自动写入几条演示数据。

- 邮箱：`zhou@example.com`
- 密码：`demo1234`

你也可以自己注册一个新账号测试。

## 部署

完整的 Vercel + Supabase 上线步骤在这里：

[deploy.md](/Users/mac/Documents/Codex/2026-06-04/rough/deploy.md)
