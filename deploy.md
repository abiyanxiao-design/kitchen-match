# 部署这个版本到 Render

## 现状

这个项目现在已经可以部署成一个真正能注册、登录、发菜、存记录的小网站。
它不依赖第三方 Python 包，所以部署方式很轻。

## 最推荐路径

推荐先上 `Render`，因为这版是 `Python + SQLite`，最需要的是：

- 一个能跑 Python 服务的 Web Service
- 一个持久化磁盘来保存 SQLite 数据
- 一条尽量少改代码的上线路径

项目已经带好了：

- `Dockerfile`
- `render.yaml`
- `Procfile`

## Render 上线步骤

1. 把这个目录放进一个 Git 仓库。
2. 推到 GitHub。
3. 登录 Render。
4. 选择 `New +` -> `Blueprint`。
5. 连接你的 GitHub 仓库。
6. 选择这个仓库，Render 会识别根目录里的 `render.yaml`。
7. 确认创建。
8. 等第一次构建完成。

这样 Render 会自动创建：

- 一个 Web Service
- 一个挂在 `/app/data` 的 persistent disk

## 如果不用 Blueprint

也可以手动新建 Web Service：

1. 选择仓库
2. Runtime 选 Docker
3. Render 会自动识别 `Dockerfile`
4. 再手动给这个服务加一个 persistent disk
5. Mount path 填 `/app/data`

## 环境变量

- `KITCHEN_HOST=0.0.0.0`
- `KITCHEN_PORT=8000`
- `KITCHEN_DATA_DIR=/app/data`

## 持久化提醒

这个版本默认用 SQLite。

如果没有 persistent disk，重启或重新部署后数据可能丢失。

Render 默认文件系统是临时的，所以 `persistent disk` 是这版上线时必须开的。

## 健康检查

健康检查地址：

- `/health`
