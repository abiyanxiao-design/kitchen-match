# 今日厨房

一个已经接上本地后端的 mobile-first 小产品。

现在它支持：

- 注册和登录
- 发一道菜
- 可选上传一张照片并预览
- 今日撞菜结果
- 本周常撞和本月厨房画像
- 我的长期记录

## 本地启动

在这个目录运行：

```bash
python3 server.py
```

然后打开：

[http://127.0.0.1:8000](http://127.0.0.1:8000)

## 测试账号

系统第一次启动会自动写入几条演示数据。

- 邮箱：`zhou@example.com`
- 密码：`demo1234`

你也可以自己注册一个新账号测试。

## 当前状态

这是一个可本地使用、可继续部署的版本。

如果要把链接发给别人直接注册使用，需要把这个目录部署到一台能公开访问的服务器上。

部署材料已经准备好了：

- [Dockerfile](/Users/mac/Documents/Codex/2026-06-04/rough/Dockerfile)
- [Procfile](/Users/mac/Documents/Codex/2026-06-04/rough/Procfile)
- [render.yaml](/Users/mac/Documents/Codex/2026-06-04/rough/render.yaml)
- [deploy.md](/Users/mac/Documents/Codex/2026-06-04/rough/deploy.md)
