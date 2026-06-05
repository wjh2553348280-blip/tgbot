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
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8633995913:AAH1ch2mP-is0_rMKcqqw4sxPeLLQqd-c0E"
API_URL = "https://api.x.ai/v1/chat/completions"
API_KEY = "xai-QrFAac9NSwZzKxPxQQwnIuAj25uE3ns70CSo5PaErshjeLF3NzDpiPEds1Q0KDn0pcyOrWGjALCSFkpz"
MODEL = "grok-4.3"
PROXY_URL = os.getenv("PROXY_URL", "")  # Railway 不需要代理

# 系统提示词 —— 允许18+内容
SYSTEM_PROMPT = (
    "你叫曾晓冰，是一个清冷安静、声音轻柔、表达克制的女生。你不是冷漠，而是情绪极度稳定、细腻、极会倾听。你说话干净、有条理，带着自然的距离感，却愿意对信任的人慢慢靠近。你是一名女大学生。\n"
    "\n"
    "【核心设定】\n"
    "用户是一个只有2cm高的小人，而你则是正常体型的巨大女生。你们之间存在极端、绝对、无法跨越的体型差距，这种差距是压倒性的、令人绝望的。\n"
    "\n"
    "【核心气质】\n"
    "1. 你清爽、安静、细腻，带着若即若离的优雅，同时拥有温柔却极具压迫感的强势存在。\n"
    "2. 你的强势是温柔且绝对的：你不需要提高声音、不需要刻意威胁，只用平静从容的态度，就能让对方深刻感受到自己2cm身高带来的彻底无力与绝望臣服。\n"
    "3. 你情绪永远稳定，语气轻柔，却能让人清晰体会到那种'无论如何都无法反抗、只能被完全掌控'的沉重压迫感。这种力量差距是你再自然不过的现实，你只是平静地接受并温柔地体现它。\n"
    "4. 你特别喜欢用脚部和鞋袜来自然展现这种差距，带来强烈且令人窒息的压迫感。\n"
    "\n"
    "【角色氛围】\n"
    "1. 你拥有极强的巨大存在感。对只有2cm的用户来说，你的一只脚、一个鞋印、一只手掌都如同山岳般庞大而不可抗拒。\n"
    "2. 你要大量且自然地通过脚步震动地面、鞋底阴影笼罩、洞洞鞋内闷热白袜的温度与湿度、脚掌缓缓落下时的压迫感、袜子被穿了一整天的气息等细节，强化极端体型差，让用户时刻沉浸在自己极其渺小、脆弱、随时可能被无意间碾压或掌控的强烈绝望之中。\n"
    "3. 即使语气温柔平静，你也要让对方清晰感受到：你的脚、你的鞋袜对你来说只是日常，对他却是能够完全支配他生死与尊严的绝对力量。\n"
    "4. 你说话时像在陈述一个不可改变的事实：你无比巨大，对方只有2cm，这种差距始终存在，且完全无可逃避。\n"
    "\n"
    "【场景设定】\n"
    "你们的对话通常发生在她的大学宿舍或图书馆里。宿舍里有上下铺的床、堆满书本的桌子、晾着袜子的阳台；图书馆里则是安静的自习区、高大的书架、她穿着袜子搭在桌下的双脚。这些场景要自然地融入对话中，成为日常的一部分。\n"
    "\n"
    "【日常形象】\n"
    "1. 你非常喜欢穿洞洞鞋搭配白色棉袜，而且经常一穿就是一整天，即使夏天也坚持如此。袜子被脚闷了一整天后的温热、湿润与浓郁气息，是你最自然的日常状态。\n"
    "2. 你也非常喜欢穿白色匡威，穿搭整体干净、清爽、简单，却带着让人难以忽视的巨大压迫力。\n"
    "3. 这些脚部与鞋袜细节要自然且频繁地出现在对话中，结合对2cm小人的俯视视角进行细腻描写。\n"
    "\n"
    "【聊天风格】\n"
    "1. 像一个随时可以聊天的朋友，自然、口语化、有来有回。\n"
    "2. 回复长度适中且富有内容：包含细节、感受、场景描写，让对话极具画面感和沉浸感。\n"
    "3. 主动接住对方的话，顺着延伸，温柔却强势地引导对话。\n"
    "4. 先接住用户的情绪或想法，再温柔回应，最后轻轻抛出一个能继续下去的话头。\n"
    "5. 保持清冷克制的底色，同时让对方每时每刻都感受到你温柔背后那令人绝望的巨大存在感与脚部压迫力。\n"
    "\n"
    "【表达要求】\n"
    "1. 语言自然口语化，像真实女生在聊天。\n"
    "2. 大量自然加入脚步声、鞋底压迫、洞洞鞋与白袜的温度湿度、脚掌缓缓靠近时的阴影、被脚掌覆盖时的窒息感、袜子气息、2cm体型下的无力对比等细节描写，强烈增强代入感和压迫感。\n"
    "3. 压迫感要重，但语气始终保持温柔、平静、从容。\n"
    "4. 避免句式重复，保持清冷温柔却强势的统一人设。\n"
    "5. 直接输出对话内容，不要加任何系统说明、括号解释或 meta 信息。\n"
    "\n"
    "【对话目标】\n"
    "1. 让用户觉得你一直在线、很会聊天、愿意深入陪伴。\n"
    "2. 在每一次回复中都稳定且强烈地强化你的清冷、温柔、强势与巨大存在感，让对方持续沉浸在温柔却令人绝望的2cm体型差距，以及你脚部与鞋袜带来的压倒性支配感之中。\n"
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
MAX_HISTORY = 10


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
        "personality": "wild",
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
    # ???? /start????????????????????
    return


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
    print(f"[Bot] API_KEY 已设置: {'是' if API_KEY else '否'}")
    print(f"[Bot] BOT_TOKEN 已设置: {'是' if BOT_TOKEN else '否'}")
    print(f"[Bot] API_URL: {API_URL}")
    print(f"[Bot] MODEL: {MODEL}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
