"""
Live2D Kiosk 插件 v2.0（队列模式）
==================================

把 astrbot 接到 Live2D 伪全息小屏幕终端。

v2.0 架构变化（板子可在任意网络，无需被访问）：
- 消息不再直连板子（旧版 POST /api/send），而是写入本插件的**消息队列**
- 板子上的"壳"程序**主动轮询**拉取队列（GET /api/v1/plugins/extensions/live2d-kiosk/pending）
- 壳拿到消息后调用板子后台 :8080/api/send 控制屏幕（表情/动作/气泡）
- 通信方向：板子壳 → astrbot 主机（主动出站，NAT 无压力）

LLM 工具（大模型分析情绪自动调用）：
  - live2d_emotion  表情（按助手自身回复情感选择）
  - live2d_action   动作
  - live2d_speak    气泡显示回复

手动指令（/屏幕 ...）与自动行为（speak_user_msg）同样写入队列。
"""
from astrbot.api.all import *
import asyncio

# 情感词 → 表情代号（Haru F 系列；Mao 用 exp_01~exp_08）
EMOTION_MAP = {
    "happy": "F01", "joy": "F01", "开心": "F01", "高兴": "F01", "哈哈": "F01",
    "angry": "F03", "mad": "F03", "生气": "F03", "愤怒": "F03", "气": "F03",
    "think": "F04", "思考": "F04", "hmm": "F04", "嗯": "F04",
    "sad": "F05", "cry": "F05", "难过": "F05", "伤心": "F05", "哭": "F05", "呜呜": "F05",
    "surprised": "F06", "wow": "F06", "惊讶": "F06", "震惊": "F06", "吓": "F06",
    "shy": "F07", "blush": "F07", "害羞": "F07", "脸红": "F07",
    "pout": "F08", "不满": "F08", "哼": "F08",
}


@register("live2d_kiosk", "mydosu", "控制 Live2D 桌面终端（队列模式：板子壳轮询拉取）", "2.0.0")
class Live2DKioskPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self._queue: list[dict] = []
        self._lock = asyncio.Lock()
        self._sessions: dict[str, dict] = {}  # origin → {last_msg, last_ts}（活跃会话）
        self.speak_user_msg = config.get("speak_user_msg", True)

        # Web API（AstrBot 自动挂载到 /api/v1/plugins/extensions/ 下并鉴权 plugin scope）
        self.context.register_web_api(
            "live2d-kiosk/pending",
            self._pending,
            ["GET"],
            "拉取待显示消息（板子壳轮询，拉取后清空）",
        )
        self.context.register_web_api(
            "live2d-kiosk/sessions",
            self._sessions_api,
            ["GET"],
            "活跃会话列表（后台下拉切换显示会话用）",
        )
        self.context.register_web_api(
            "live2d-kiosk/ping",
            self._ping,
            ["GET"],
            "探活",
        )

    # ================= Web API =================
    async def _ping(self):
        return {"status": "ok", "plugin": "live2d-kiosk"}

    async def _pending(self):
        """板子壳轮询：返回队列并清空"""
        async with self._lock:
            msgs = self._queue
            self._queue = []
        return {"ok": True, "messages": msgs}

    async def _sessions_api(self):
        """活跃会话列表：origin → 最后消息/时间"""
        return {"ok": True, "sessions": self._sessions}

    async def _enqueue(self, payload: dict, origin: str | None = None):
        if origin:
            payload["origin"] = origin
        async with self._lock:
            self._queue.append(payload)

    def _touch_session(self, event: AstrMessageEvent):
        """记录活跃会话（消息来源）"""
        origin = getattr(event, "unified_msg_origin", None) or getattr(
            getattr(event, "message_obj", None), "session_id", None
        )
        if origin:
            self._sessions[origin] = {
                "last_msg": (event.message_str or "")[:40],
                "last_ts": __import__("time").time(),
            }
        return origin

    # ================= LLM 工具（写队列） =================
    @llm_tool(name="live2d_emotion")
    async def live2d_emotion(self, event: AstrMessageEvent, emotion: str):
        """控制屏幕上的 Live2D 模型表情。在你（助手）开口回复之前调用：表情应反映你这句话想表达的情感——比如你开心地答应就用 happy，安慰对方就用 sad 或 shy，被逗笑就用 surprised，觉得对方无理取闹就用 angry。这是你表达自己情绪的方式，不是转述用户的情绪。

        Args:
            emotion(string): 你这句话的情感。情感词自动映射：happy→F01（开心）, angry→F03（生气）, think→F04（思考）, sad→F05（难过）, surprised→F06（惊讶）, shy→F07（害羞）, pout→F08（不满）；也可直接填代号 F01~F08（Haru 模型）或 exp_01~exp_08（Mao 模型）。
        """
        emo = self._map_emotion(emotion)
        origin = self._touch_session(event)
        await self._enqueue({"type": "emotion", "value": emo}, origin)
        return f"表情 {emo} 已发送到屏幕"

    @llm_tool(name="live2d_action")
    async def live2d_action(self, event: AstrMessageEvent, action: str):
        """触发屏幕 Live2D 模型的动作，配合你说话时的肢体语言（如开心时挥手、打招呼时招手、提到"拍一下"时轻拍身体）。在说话前或说话的同时调用。

        Args:
            action(string): 动作代号。常用：tapbody_0（轻拍身体）、tap（点击互动）、idle（待机）、wave（挥手）；也可以填组名加编号如 tapbody_1。
        """
        origin = self._touch_session(event)
        await self._enqueue({"type": "action", "value": action}, origin)
        return f"动作 {action} 已发送到屏幕"

    @llm_tool(name="live2d_speak")
    async def live2d_speak(self, event: AstrMessageEvent, text: str):
        """把你要说的话显示在屏幕的对话气泡中（相当于模型"说"出来）。当你准备回复用户时调用，把完整回复内容显示到屏幕上，让对话在屏幕上可见。

        Args:
            text(string): 你要显示的回复内容（200 字以内）。
        """
        origin = self._touch_session(event)
        await self._enqueue({"type": "speak", "text": text[:200]}, origin)
        return f"已在屏幕显示：{text[:80]}"

    # ================= 手动指令 =================
    @event_message_type(EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        msg = (event.message_str or "").strip()
        if not msg:
            return
        origin = self._touch_session(event)
        if msg.startswith(("/屏幕", "/screen", "/kiosk")):
            yield event.result(await self._handle_cmd(msg, origin))
            return
        # 普通消息：可选转发气泡（写队列，由板子壳显示；带会话来源）
        if self.speak_user_msg:
            await self._enqueue({"type": "speak", "text": f"你：{msg[:80]}"}, origin)

    async def _handle_cmd(self, msg: str, origin: str | None = None) -> str:
        parts = msg.split(maxsplit=1)
        if len(parts) == 1:
            return self._help()
        _, rest = parts
        sub = rest.split(maxsplit=1)
        action = sub[0]
        arg = sub[1].strip() if len(sub) > 1 else ""

        if action in ("表情", "emotion"):
            if not arg:
                return "用法：/屏幕 表情 <代号或情感词>（如 happy、F01、exp_05）"
            emo = self._map_emotion(arg)
            await self._enqueue({"type": "emotion", "value": emo}, origin)
            return f"表情 {emo} 已发送到屏幕 ✅"
        if action in ("动作", "action"):
            if not arg:
                return "用法：/屏幕 动作 <代号>（如 tapbody_0、tap、idle）"
            await self._enqueue({"type": "action", "value": arg}, origin)
            return "动作已发送到屏幕 ✅"
        if action in ("说", "speak", "say"):
            if not arg:
                return "用法：/屏幕 说 <内容>"
            await self._enqueue({"type": "speak", "text": arg[:200]}, origin)
            return "已发送到屏幕 ✅"
        if action in ("帮助", "help"):
            return self._help()
        return "未知指令，/屏幕 帮助 查看用法"

    @staticmethod
    def _help() -> str:
        return (
            "📺 Live2D 屏幕控制（队列模式）\n"
            "/屏幕 表情 <代号>  切换表情（happy、F01、exp_05）\n"
            "/屏幕 动作 <代号>  触发动作（tapbody_0、tap、idle）\n"
            "/屏幕 说 <内容>    气泡显示文字\n"
            "大模型已获得表情/动作/说话工具（自动入队，由板子壳显示到屏幕）"
        )

    @staticmethod
    def _map_emotion(value: str) -> str:
        v = value.strip()
        if not v:
            return "F01"
        low = v.lower()
        if low.startswith(("f0", "exp_")):
            return v
        return EMOTION_MAP.get(low, EMOTION_MAP.get(v, "F01"))
