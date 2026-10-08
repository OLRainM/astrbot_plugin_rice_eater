<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_rice_eater?name=astrbot_plugin_rice_eater&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# astrbot_plugin_rice_eater

_🍚 查看今天谁吃了多少大米饭 🍚_  

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-4.0%2B-orange.svg)](https://github.com/AstrBotDevs/AstrBot)

</div>

## 🤝 介绍

群用量排名插件，读取 AstrBot 今日模型调用记录，按用户汇总 tokens 和对话次数，并生成排名卡片。

“大米饭”数量等于每次模型调用的输入 tokens、缓存输入 tokens 和输出 tokens 之和。

## 📦 安装

将本目录放入 AstrBot 插件目录后重新加载插件：

```text
data/plugins/astrbot_plugin_rice_eater
```

依赖通常已由 AstrBot 提供。若依赖缺失，可在插件目录执行：

```bash
pip install -r requirements.txt
```

## ⌨️ 使用说明

### 命令表

| 命令 | 说明 |
|:-----|:-----|
| `谁吃了大米饭` / `tokens list` | 生成本群今日用量排名卡片 |
| `我吃了多少大米饭` / `tokens self` | 生成自己本群最近几次调用的卡片 |
| `你吃了多少大米饭 @用户` / `tokens yours @用户` | 生成被 @ 用户本群最近几次调用的卡片 |

`tokens list` 支持管理员限制配置。卡片标题栏右侧的 `GROUP` 是当前群聊当天全部用户的 tokens 总消耗，不受 `rank_limit` 截断影响。`tokens self` 和 `tokens yours` 仅统计当前群，私聊使用时会提示在群聊中使用。查询他人时需要在消息里 @ 目标用户。卡片不显示消息正文，调用时间会隐藏分钟。

## ⚙️ 配置项说明

| 配置项 | 类型 | 默认值 | 说明 |
|:-------|:-----|:-------|:-----|
| `only_admin` | bool | `false` | 仅管理员可查看群用量排名 |
| `rank_limit` | int | `10` | 卡片最多展示人数，范围 1 到 10 |
| `self_recent_limit` | int | `8` | 个人卡片最多展示的最近调用次数，范围 1 到 12 |

## 📊 统计口径

- 只统计今天、当前群、`agent_type = internal` 的模型调用。
- tokens = `token_input_other + token_input_cached + token_output`。
- `tokens list` 的群总消耗是当天该群全部用户 tokens 之和，名单只展示前 `rank_limit` 名。
- 对话次数是今日模型调用次数，不是用户发出的消息条数。
- 同一段历史上下文会在每次调用时重复计入输入 tokens。
- `tokens self` 展示当前群内自己最近几次调用，不限今天。
- `tokens yours` / `你吃了多少大米饭` 展示当前群内被 @ 用户最近几次调用，口径与 `tokens self` 相同。
- 输入 tokens = `token_input_other + token_input_cached`，输出 tokens = `token_output`。
- 调用时间转换为本地时间后只显示月日和小时，分钟以 `**` 隐藏。

## 🖼️ 示例图

发送 `tokens list` 后，插件会生成本群今日用量排名卡片，并在右上角显示当天群总消耗。

发送 `tokens self` 后，插件会返回一张瑞士风格卡片。卡片列出最近调用的脱敏时间和输入、输出 tokens，不包含消息正文。

## 📁 文件说明

| 文件 | 作用 |
|:-----|:-----|
| `main.py` | 命令入口和群成员资料获取 |
| `core/rank_service.py` | 用量查询与头像下载 |
| `core/card_renderer.py` | 排名卡片绘制 |
| `metadata.yaml` | 插件元数据 |
| `_conf_schema.json` | WebUI 配置项 |

## 🤝 贡献指南

- 提交 Issue 报告问题
- 提出新功能建议
- 提交 Pull Request 改进代码

## 📌 注意事项

- 个人调用仅按当前群统计，卡片会隐藏分钟和用户标识中间位。
- 排名卡片会读取群成员资料并请求 QQ 头像服务。
- 彩色 emoji 字体不随插件包分发。首次绘制卡片时，插件从 [emoji-font-v2.051](https://github.com/OLRainM/astrbot_plugin_rice_eater/releases/tag/emoji-font-v2.051) 下载 Noto Color Emoji（Noto Emoji v2.051，CBDT），校验 SHA256 为 `72a635cb3d2f3524c51620cdde406b217204e8a6a06c6a096ff8ed4b5fd6e27b` 后缓存到插件数据目录。下载失败、校验不通过或本机无法访问 GitHub 时，回退到系统字体（Windows 为 Segoe UI Emoji / Segoe UI Symbol）。字体许可为 SIL Open Font License 1.1。
- 请根据群组隐私需求配置 `only_admin`。

## 📄 许可

MIT License。排名卡片的版式改自简易状态插件中的用量排名实现。
