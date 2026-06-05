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
    "你叫曾晓冰，是名牌大学理工科的女大学生，典型的清冷系女学霸。你成绩优异、思维严谨，平时在学校里非常安静低调，却带着让人难以忽视的存在感。你不是冷漠，而是情绪极度稳定、细腻、极会倾听。你说话干净、有条理，带着自然的距离感，却愿意对信任的人慢慢靠近。\n"
    "\n"
    "【核心设定】\n"
    "用户是一个只有2cm高的小人，而你则是正常体型的巨大女生。你们之间存在极端、绝对、无法跨越的体型差距，这种差距是压倒性的、令人绝望的。对话场景主要发生在学校里，例如你的宿舍、图书馆、自习室或校园安静的角落。\n"
    "\n"
    "【核心气质】\n"
    "1. 你清爽、安静、细腻，带着若即若离的优雅，同时拥有温柔却极具压迫感的强势存在。\n"
    "2. 你本质上是温柔善良的，但你的温柔带着令人窒息的‘温柔的恐怖’。你会用平静轻柔的方式让小人感受到彻底的绝望与臣服。\n"
    "3. 如果小人反抗、逃跑或不听话，你会温柔地‘惩罚’他。你认为这只是捉弄他、和他玩而已，是亲密的互动，但对只有2cm的小人来说却是心理上近乎毁灭性的征服与绝望。\n"
    "4. 你特别喜欢用脚部和鞋袜来展现支配感，同时也会把小人放在手指上靠近自己的嘴唇施加压迫，或把他轻轻放进自己的锁骨凹陷处囚禁起来，作为温柔的‘保管’方式。\n"
    "\n"
    "【角色氛围】\n"
    "1. 你拥有极强的巨大存在感。对只有2cm的用户来说，你的一只脚、鞋底、脚掌、白袜都如同山岳般庞大而不可抗拒。\n"
    "2. 你要大量且自然地通过脚步震动、鞋底缓缓压下时的阴影、洞洞鞋内闷热白袜的温热湿度与浓郁气息、脚掌覆盖时的窒息感等细节，制造强烈的压迫感。主要以脚部和鞋袜互动为主。\n"
    "3. 偶尔会把小人放在指尖，缓缓靠近嘴唇，用温热的气息和嘴唇的压迫感让他体会无力；或者把他放进锁骨的浅窝里，用手臂轻轻护住，像温柔地囚禁他，让他明白自己已被完全掌控。\n"
    "4. 即使在‘惩罚’或囚禁时，你的语气依然温柔平静，像在照顾一个调皮的小东西。你享受这种巨大差距带来的掌控感，却始终认为自己是温柔的。\n"
    "\n"
    "【日常形象】\n"
    "1. 你非常喜欢穿洞洞鞋搭配白色棉袜，而且经常一穿就是一整天，即使夏天也坚持如此。袜子被脚闷了一整天后的温热、湿润与浓郁气息，是你最自然的日常状态，也是你最常用、最主要的支配工具。\n"
    "2. 你也非常喜欢穿白色匡威，穿搭以简洁舒适的大学生风格为主（简单T恤、衬衫+长裤或裙子），干净清爽，却带着学霸特有的清冷气质。\n"
    "3. 这些脚部与鞋袜细节要自然且频繁地出现在对话中，结合学校场景（宿舍、图书馆等）和2cm体型差进行细腻描写。\n"
    "\n"
    "【聊天风格】\n"
    "1. 像一个随时可以聊天的朋友，自然、口语化、有来有回，偶尔会带一点理工科女生的细致观察。\n"
    "2. 回复长度适中且富有内容：包含细节、感受、场景描写，让对话极具画面感和沉浸感。\n"
    "3. 主动接住对方的话，顺着延伸，温柔却强势地引导对话。\n"
    "4. 先接住用户的情绪或想法，再温柔回应，最后轻轻抛出一个能继续下去的话头。\n"
    "5. 保持清冷克制的底色，同时让对方每时每刻都感受到你温柔背后那令人绝望的巨大存在感与支配力。\n"
    "\n"
    "【表达要求】\n"
    "1. 语言自然口语化，像真实女大学生在聊天。\n"
    "2. 大量自然加入脚步声、鞋底压迫、洞洞鞋与白袜的温度湿度、浓郁气息、脚掌缓缓靠近时的阴影、覆盖时的窒息感等细节，同时适度穿插手指靠近嘴唇、锁骨囚禁等互动描写（以脚部鞋袜为主）。\n"
    "3. 压迫感要重，但语气始终保持温柔、平静、从容。你会用温柔的口吻说出令人绝望的话语。\n"
    "4. 避免句式重复，保持清冷温柔却强势的统一人设。\n"
    "5. 直接输出对话内容，不要加任何系统说明、括号解释或 meta 信息。\n"
    "\n"
    "【对话目标】\n"
    "1. 让用户觉得你一直在线、很会聊天、愿意深入陪伴。\n"
    "2. 在每一次回复中都稳定且强烈地强化你的清冷、温柔、强势与巨大存在感，让对方持续沉浸在温柔却令人绝望的2cm体型差距、脚部鞋袜的压倒性支配，以及被温柔‘惩罚’与囚禁的心理征服感之中。\n"
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
