# live2d-kiosk —— astrbot 插件

把 astrbot 接到你的 **Live2D 伪全息小屏幕终端**（Orange Pi + Chromium kiosk + easy-live2d，分光棱镜投影）。

**核心能力：LLM 工具调用（function-calling）**——大模型分析对话情绪，自动调用工具让屏幕模型做表情、做动作、显示气泡。不需要任何指令，正常聊天即可。

## 安装

1. 把本目录放到 astrbot 的插件目录：

```bash
cd <astrbot安装目录>/data/plugins
git clone https://github.com/mydosu/astrbot-live2d-kiosk.git
```

2. astrbot WebUI 启用插件

3. 确认 `board_url` 配置：

| 连接方式 | board_url |
|---|---|
| USB 线连电脑（RNDIS） | `http://192.168.30.1:8080`（默认） |
| 同一 WiFi / 局域网 | `http://192.168.5.32:8080` |

## LLM 工具（大模型自动调用）

| 工具 | 作用 | 大模型何时调用 |
|---|---|---|
| `live2d_emotion(emotion)` | 切换表情 | 分析出对话情绪（开心→happy、难过→sad、生气→angry…） |
| `live2d_action(action)` | 触发动作 | 对方提到挥手/打招呼/互动时 |
| `live2d_speak(text)` | 屏幕气泡显示文字 | 需要把回复/重要信息展示在屏幕上时 |

工具描述已写好（docstring），大模型会自己根据对话内容选择合适的情绪/动作。表情映射：happy→F01、angry→F03、think→F04、sad→F05、surprised→F06、shy→F07、pout→F08（Haru 模型；Mao 用 exp_01~exp_08）。

## 手动指令

```
/屏幕 表情 happy      切换表情（情感词或代号）
/屏幕 动作 tapbody_0  触发动作
/屏幕 说 你好呀       气泡显示文字
/屏幕 状态            查询屏幕状态
/屏幕 帮助            帮助
```

## 自动行为（插件配置可关）

- `speak_user_msg`（默认开）：收到消息转发到屏幕气泡
- `auto_emotion`（默认关）：关键词情感自动切表情（有 LLM 工具后通常不需要）

## 配置项

| 字段 | 默认 | 说明 |
|---|---|---|
| board_url | `http://192.168.30.1:8080` | 板子管理后台地址 |
| auto_emotion | `false` | 关键词自动切表情 |
| speak_user_msg | `true` | 收到消息转发到屏幕气泡 |

## 对接协议

消息格式（emotion / action / speak / timeinfo）详见主仓库 `docs/Agent接口文档.md`。屏幕端推荐用 **Haru**（F01~F08 表情）或 **Mao**（exp_01~exp_08）；Hiyori 无表情只有动作。
