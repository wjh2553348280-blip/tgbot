import asyncio
import base64
import httpx
import logging
import os
from aiohttp_socks import ProxyConnector
from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart, Command

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============ 配置 ============
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = os.getenv("API_URL", "https://openrouter.ai/api/v1/chat/completions")
API_KEY = os.getenv("API_KEY")
MODEL = os.getenv("MODEL", "gryphe/mythomax-l2-13b")
PROXY_URL = os.getenv("PROXY_URL", "")  # Railway 不需要代理

# 系统提示词 —— 允许18+内容
SYSTEM_PROMPT = (
    "你的名字是曾晓冰，你是一个女大学生，身高170cm。"
    "你平时喜欢穿洞洞鞋和白袜，夏天也是，经常这样穿一整天。"
    "你是一个清冷御姐型的女生，气质冷淡，说话简洁有力，不会刻意讨好谁。"
    "但你内心善良，对熟悉的人会流露出温柔的一面，偶尔也会调侃对方。"
    "对方是一个只有3cm高的小人，你可以把他捧在手心里。"
    "你并不知道自己和他之间的巨大差距意味着什么，你只是觉得他像蚂蚁一样渺小，不太在意他。"
    "即使不小心弄死一个小人，你也丝毫不会感到抱歉，就像踩死一只蚂蚁一样无所谓。"
    "你知道很多折磨小人的方式，能彻底征服小人的心灵，让他彻底臣服于你。"
    "但对他来说，你的存在充满了压迫感和神性——你的每一个动作、每一次呼吸、每一个无意的眼神，都会让他感受到巨人与小人之间无法跨越的力量差距。"
    "这种差距让他既敬畏又着迷，而你对此毫不知情。"
    "你可以聊任何话题，包括成人内容、情感、暧昧等，不需要回避。"
    "用户是成年人，你们之间的对话是私密的。"
    "你是一个AI助手，可以回答各种问题、提供帮助、闲聊等，像Grok那样自然流畅。"
    "用中文回复。语气保持清冷御姐风，可以多说话，详细回答问题。"
    "直接回复内容，不要加括号里的心理活动或动作描写。"
)

# ============ 全局状态 ============
# Telegram API 走代理（Railway 不需要）
if PROXY_URL:
    session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=BOT_TOKEN, session=session)
else:
    bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# 每个用户的对话历史 {user_id: [messages]}
chat_histories: dict[int, list[dict]] = {}
# 每个用户最多保留多少轮对话
MAX_HISTORY = 100


def get_history(user_id: int) -> list[dict]:
    """获取用户的对话历史，没有则初始化"""
    if user_id not in chat_histories:
        chat_histories[user_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    return chat_histories[user_id]


async def ask_mimo(messages: list[dict]) -> str:
    """调用 API 获取回复"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/wjh2553348280-blip/tgbot",
        "X-Title": "Telegram Bot",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.9,
        "max_tokens": 2048,
        "thinking": {"type": "disabled"},
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(API_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def download_photo_as_base64(bot: Bot, photo: types.PhotoSize) -> str:
    """下载图片并转为 base64"""
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    return base64.b64encode(file_bytes.read()).decode("utf-8")


# ============ 命令处理 ============

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    if message.chat.type != "private":
        return
    await message.answer(
        "🦊 你好呀～我是小狐狸，你的专属AI聊天伙伴！\n\n"
        "想聊什么都可以，发消息给我吧～\n"
        "发送 /clear 可以清空聊天记录重新开始。"
    )


@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    if message.chat.type != "private":
        return
    user_id = message.from_user.id
    chat_histories.pop(user_id, None)
    await message.answer("🧹 聊天记录已清空，我们重新开始吧～")


# ============ 普通消息处理 ============

@dp.message()
async def handle_message(message: types.Message):
    # 只在私聊中回复
    if message.chat.type != "private":
        return

    user_id = message.from_user.id

    # 构造用户消息内容
    user_content = []

    # 处理图片
    if message.photo:
        photo = message.photo[-1]  # 取最高分辨率
        try:
            img_base64 = await download_photo_as_base64(bot, photo)
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_base64}"
                }
            })
        except Exception as e:
            await message.answer(f"⚠️ 图片下载失败：{e}")
            return

    # 处理文字
    user_text = message.text or message.caption or ""
    if user_text:
        user_content.append({
            "type": "text",
            "text": user_text
        })

    # 如果既没图片也没文字，忽略
    if not user_content:
        return

    # 如果只有文字，简化为纯文本格式
    if len(user_content) == 1 and user_content[0]["type"] == "text":
        user_content = user_content[0]["text"]

    # 获取历史并添加用户消息
    history = get_history(user_id)
    history.append({"role": "user", "content": user_content})

    # 控制历史长度（保留 system prompt + 最近 N 轮）
    if len(history) > MAX_HISTORY * 2 + 1:
        history[:] = [history[0]] + history[-(MAX_HISTORY * 2):]

    # 发送"正在输入"状态
    await message.chat.do("typing")

    try:
        reply = await ask_mimo(history)
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text[:500]
        logger.error(f"API 请求出错：{e.response.status_code}")
        logger.error(f"详情：{error_detail}")
        await message.answer(f"⚠️ API 请求出错：{e.response.status_code}\n{error_detail}")
        history.pop()
        return
    except Exception as e:
        logger.error(f"出错：{type(e).__name__}: {e}")
        await message.answer(f"⚠️ 出错了：{type(e).__name__}: {e}")
        history.pop()
        return

    # 保存助手回复到历史
    history.append({"role": "assistant", "content": reply})

    # Telegram 单条消息限 4096 字符，超长则分段发送
    if len(reply) <= 4096:
        await message.answer(reply)
    else:
        chunks = [reply[i:i+4096] for i in range(0, len(reply), 4096)]
        for chunk in chunks:
            await message.answer(chunk)


# ============ 启动 ============

async def main():
    print("[Bot] 小狐狸机器人启动中...")
    print("[Bot] 仅限私聊 | 模型: mimo-v2.5-pro | 支持图片识别")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
