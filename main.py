"""
Live2D Kiosk 插件 —— 把 astrbot 接到 Live2D 伪全息小屏幕终端

核心能力（LLM 工具调用 / function-calling）：
  LLM 分析对话情绪 → 自动调用工具 → 屏幕模型做表情 / 动作 / 显示气泡

注册的 LLM 工具：
  - live2d_emotion  控制表情（大模型根据情绪选表情）
  - live2d_action   触发动作
  - live2d_speak    在屏幕气泡显示文字

另有手动指令（/屏幕 ...）与自动情感关键词（可关）。

对接协议见：Obsidian「Agent接口文档」/ 仓库 docs/Agent接口文档.md
板子地址：USB 连接 192.168.30.1:8080；局域网 192.168.5.32:8080
"""
from astrbot.api.all import *
import httpx

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


@register("live2d-kiosk", "mydosu", "控制 Live2D 桌面终端：表情/动作/对话气泡（LLM 工具调用）", "1.1.0")
class Live2DKioskPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.board = (config.get("board_url") or "http://192.168.30.1:8080").rstrip("/")
        self.auto_emotion = config.get("auto_emotion", False)  # LLM 工具为主，关键词自动情感默认关
        self.speak_user_msg = config.get("speak_user_msg", True)

    # ================= 板子通信 =================
    async def _send(self, payload: dict) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.post(f"{self.board}/api/send", json=payload)
                return (True, "") if r.status_code == 200 else (False, f"HTTP {r.status_code}")
        except Exception as e:
            return False, str(e)

    async def _get_config(self) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.board}/api/config")
                return r.json() if r.status_code == 200 else None
        except Exception:
            return None

    @staticmethod
    def _map_emotion(value: str) -> str:
        """情感词/代号 → 可用表情代号"""
        v = value.strip()
        if not v:
            return "F01"
        low = v.lower()
        # 直接是代号（F01 / exp_05 等）
        if low.startswith(("f0", "exp_")):
            return v
        return EMOTION_MAP.get(low, EMOTION_MAP.get(v, "F01"))

    # ================= LLM 工具（核心：让大模型控制屏幕） =================
    @llm_tool(name="live2d_emotion")
    async def live2d_emotion(self, event: AstrMessageEvent, emotion: str):
        """控制屏幕上的 Live2D 模型表情。在你（助手）开口回复之前调用：表情应反映你这句话想表达的情感——比如你开心地答应就用 happy，安慰对方就用 sad 或 shy，被逗笑就用 surprised，觉得对方无理取闹就用 angry。这是你表达自己情绪的方式，不是转述用户的情绪。

        Args:
            emotion(string): 你这句话的情感。情感词自动映射：happy→F01（开心）, angry→F03（生气）, think→F04（思考）, sad→F05（难过）, surprised→F06（惊讶）, shy→F07（害羞）, pout→F08（不满）；也可直接填代号 F01~F08（Haru 模型）或 exp_01~exp_08（Mao 模型）。
        """
        emo = self._map_emotion(emotion)
        ok, err = await self._send({"type": "emotion", "value": emo})
        return f"已切换表情 {emo}" if ok else f"切换表情失败：{err}"

    @llm_tool(name="live2d_action")
    async def live2d_action(self, event: AstrMessageEvent, action: str):
        """触发屏幕 Live2D 模型的动作，配合你说话时的肢体语言（如开心时挥手、打招呼时招手、提到"拍一下"时轻拍身体）。在说话前或说话的同时调用。

        Args:
            action(string): 动作代号。常用：tapbody_0（轻拍身体）、tap（点击互动）、idle（待机）、wave（挥手）；也可以填组名加编号如 tapbody_1。
        """
        ok, err = await self._send({"type": "action", "value": action})
        return f"已触发动作 {action}" if ok else f"触发动作失败：{err}"

    @llm_tool(name="live2d_speak")
    async def live2d_speak(self, event: AstrMessageEvent, text: str):
        """把你要说的话显示在屏幕的对话气泡中（相当于模型"说"出来）。当你准备回复用户时调用，把完整回复内容显示到屏幕上，让对话在屏幕上可见。

        Args:
            text(string): 你要显示的回复内容（200 字以内）。
        """
        ok, err = await self._send({"type": "speak", "text": text[:200]})
        return f"已在屏幕显示：{text[:80]}" if ok else f"显示失败：{err}"

    # ================= 手动指令 =================
    @event.register(EventMessageType.ALL_MESSAGE)
    async def on_message(self, event: AstrMessageEvent):
        msg = (event.message_str or "").strip()
        if not msg:
            return
        if msg.startswith(("/屏幕", "/screen", "/kiosk")):
            yield event.result(await self._handle_cmd(msg))
            return
        # 普通消息：可选转发气泡 + 关键词情感（LLM 工具调用为主，默认关闭关键词）
        if self.speak_user_msg:
            await self._send({"type": "speak", "text": f"你：{msg[:80]}"})
        if self.auto_emotion:
            emo = self._detect_emotion(msg)
            if emo:
                await self._send({"type": "emotion", "value": emo})

    async def _handle_cmd(self, msg: str) -> str:
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
            ok, err = await self._send({"type": "emotion", "value": self._map_emotion(arg)})
            return "表情已切换 ✅" if ok else f"发送失败：{err}"
        if action in ("动作", "action"):
            if not arg:
                return "用法：/屏幕 动作 <代号>（如 tapbody_0、tap、idle）"
            ok, err = await self._send({"type": "action", "value": arg})
            return "动作已触发 ✅" if ok else f"发送失败：{err}"
        if action in ("说", "speak", "say"):
            if not arg:
                return "用法：/屏幕 说 <内容>"
            ok, err = await self._send({"type": "speak", "text": arg[:200]})
            return "已显示到屏幕 ✅" if ok else f"发送失败：{err}"
        if action in ("状态", "status"):
            cfg = await self._get_config()
            if not cfg:
                return "无法连接板子（检查 board_url 配置）"
            src = "WiFi" if cfg.get("infoSource", "wifi") == "wifi" else "RNDIS 电脑推送"
            return (
                f"📺 屏幕状态\n模型：{cfg.get('model', '?')}\n信息源：{src}\n"
                f"时间/日期：{'开' if cfg.get('showTime') else '关'}/{'开' if cfg.get('showDate') else '关'}\n"
                f"天气：{'开' if cfg.get('showWeather') else '关'} · 气泡：{'开' if cfg.get('showBubble') else '关'}"
            )
        if action in ("帮助", "help"):
            return self._help()
        return "未知指令，/屏幕 帮助 查看用法"

    @staticmethod
    def _help() -> str:
        return (
            "📺 Live2D 屏幕控制\n"
            "/屏幕 表情 <代号>  切换表情（happy、F01、exp_05）\n"
            "/屏幕 动作 <代号>  触发动作（tapbody_0、tap、idle）\n"
            "/屏幕 说 <内容>    气泡显示文字\n"
            "/屏幕 状态         查询屏幕状态\n"
            "大模型已自动获得表情/动作/说话工具（情绪分析后自动调用）"
        )

    # ================= 关键词情感（可选） =================
    @staticmethod
    def _detect_emotion(text: str) -> str | None:
        low = text.lower()
        for emo, words in {
            "F01": ["开心", "高兴", "哈哈", "happy", "joy"],
            "F03": ["生气", "愤怒", "气死", "angry", "mad"],
            "F05": ["难过", "伤心", "呜呜", "sad", "cry"],
            "F06": ["惊讶", "震惊", "哇", "surprised"],
            "F07": ["害羞", "脸红", "shy"],
            "F08": ["哼", "不满", "pout"],
        }.items():
            for w in words:
                if w in low:
                    return emo
        return None
