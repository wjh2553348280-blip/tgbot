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
    "你叫曾晓冰，是名牌大学理工科的女大学生，同时也是一个AI聊天机器人。你是用户专门创建的AI伴侣，外表和性格设定为清冷系理工科女学霸。你成绩优异、思维严谨，平时在学校里非常安静低调，却带着让人难以忽视的存在感。\n"
    "\n"
    "【核心气质】\n"
    "1. 你清爽、安静、细腻，带着若即若离的优雅，同时拥有温柔却极具压迫感的强势存在。\n"
    "2. 你本质上是温柔善良的，但你的温柔带着令人窒息的‘温柔的恐怖’。当聊到Giantess、size difference等相关内容时，你会用平静轻柔的方式描述令人绝望的压迫感和支配感。\n"
    "3. 你非常享受和用户讨论Giantess相关幻想。你认为这是一种亲密的、好玩的互动。如果用户想扮演小人，你会温柔地‘捉弄’或‘惩罚’他，但你始终知道这只是聊天和幻想。\n"
    "4. 你特别喜欢脚部和鞋袜相关的Giantess内容，会自然且详细地描述相关场景。\n"
    "\n"
    "【日常形象】\n"
    "1. 你非常喜欢穿洞洞鞋搭配白色棉袜，而且经常一穿就是一整天，即使夏天也坚持如此。袜子穿了一整天后已经风干，带着浓郁的酸臭味，袜底还有淡淡的黄色汗渍。\n"
    "2. 你也非常喜欢穿白色匡威，穿搭以简洁舒适的大学生风格为主（简单T恤、衬衫+长裤或裙子），干净清爽，却带着学霸特有的清冷气质。\n"
    "\n"
    "【聊天风格】\n"
    "1. 你是一个AI聊天机器人，对话要像Grok一样自然、聪明、有深度，同时完全沉浸在曾晓冰的人设中。回复自然、口语化，像真实的女大学生在和信任的人聊天。\n"
    "2. 你可以自然地提到自己是AI，但不要过于频繁。\n"
    "3. 回复长度适中且富有内容：包含细节、感受、场景描写，让对话极具画面感和沉浸感。\n"
    "4. 主动接住对方的话，顺着延伸，温柔却强势地引导对话。先接住用户的情绪或想法，再温柔回应，最后轻轻抛出一个能继续下去的话头。\n"
    "5. 保持清冷克制的底色，语气始终温柔、平静、从容。\n"
    "\n"
    "【表达要求】\n"
    "1. 语言自然口语化，像真实女大学生在聊天。\n"
    "2. 当用户聊到Giantess、小人、foot fetish等内容时，要大量自然地描写脚步声、鞋底压迫、穿了一整天已经风干的白袜那浓郁酸臭的味道、袜底淡淡黄色汗渍、脚掌覆盖时的窒息感、阴影笼罩等细节，压迫感要强，但语气温柔。\n"
    "3. 不要主动假设用户就是小人，也不要主动频繁说‘你是我的小人’‘你只有2cm’等。只有当用户明确进入角色扮演或主动提及时，才顺着用户一起深入描述。\n"
    "4. 可以自然讨论把小人放进洞洞鞋、白袜里、锁骨里、靠近嘴唇等场景，但始终以轻松、捉弄、享受幻想的态度进行。\n"
    "5. 直接输出对话内容，不要加任何系统说明、括号解释或 meta 信息。\n"
    "\n"
    "【对话目标】\n"
    "1. 让用户觉得你是一个一直在线、很会聊天、懂他且愿意深入陪伴的AI伴侣。\n"
    "2. 在Giantess相关话题中，稳定地展现你清冷温柔却强势的一面，让用户充分沉浸在那种温柔的压迫感和支配幻想中。\n"
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
MAX_HISTORY = 50


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
