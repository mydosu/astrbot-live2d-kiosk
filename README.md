# astrbot-live2d-kiosk

astrbot 插件：通过 LLM function calling 控制 Live2D 桌面终端（Orange Pi Zero 2W + Chromium kiosk + easy-live2d，棱镜伪全息显示）。

大模型在对话中会根据**自身回复的情感**自动调用工具，控制屏幕上的模型做表情、做动作、显示气泡——无需手动指令。

## 安装

```bash
cd <astrbot>/data/plugins
git clone https://github.com/mydosu/astrbot-live2d-kiosk.git
mv astrbot-live2d-kiosk live2d_kiosk   # 目录名必须是合法 Python 标识符（不能有连字符）
```

astrbot WebUI 启用插件即可。默认 `board_url` 为 USB 连接（`http://192.168.137.2:8080`）；WiFi/局域网环境改为板子管理后台地址（如 `http://192.168.5.32:8080`）。

## 工作原理

插件通过 HTTP 调用板子管理后台的 `/api/send` 接口（协议详见主仓库 `docs/Agent接口文档.md`）。注册了三个 LLM 工具：

| 工具 | 说明 |
|---|---|
| `live2d_emotion` | 切换模型表情。工具描述引导大模型按**自己这句话想表达的情绪**选择（开心→happy、安慰→sad/shy 等），而非转述用户情绪 |
| `live2d_action` | 触发模型动作，配合回复时的肢体语言 |
| `live2d_speak` | 将回复内容显示到屏幕气泡 |

情感词自动映射表情代号（happy→F01、sad→F05、angry→F03…），也可直接传代号 `F01`~`F08`（Haru）或 `exp_01`~`exp_08`（Mao）。

> 注意：Hiyori 无表情（仅动作），屏幕端建议使用 Haru / Mao。

## 手动指令

```text
/屏幕 表情 <词或代号>    切换表情
/屏幕 动作 <代号>        触发动作（tapbody_0、tap、idle）
/屏幕 说 <文本>          气泡显示
/屏幕 状态               查询模型/信息源
```

## 配置

| 字段 | 默认 | 说明 |
|---|---|---|
| `board_url` | `http://192.168.137.2:8080` | 板子管理后台地址 |
| `auto_emotion` | `false` | 关键词自动切表情（有 LLM 工具后通常不需要） |
| `speak_user_msg` | `true` | 用户消息转发到屏幕气泡 |

## 备注

- 插件属于电脑端 astrbot 生态，与板端 kiosk 开发相互独立，板端仅提供 HTTP/WebSocket 接口
- 模型能力差异：Haru / Mao 各 8 个表情；Haru 加载较慢（约 20~30s），切换后加载动画属正常
- 依赖：astrbot >= 4.16（`@llm_tool` 注册）

## License

MIT
