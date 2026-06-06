import asyncio
import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import AsyncIterator

import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command, CommandStart


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


BOT_TOKEN = os.getenv("BOT_TOKEN") or "8633995913:AAH1ch2mP-is0_rMKcqqw4sxPeLLQqd-c0E"
API_URL = "https://api.x.ai/v1/chat/completions"
API_KEY = "xai-QrFAac9NSwZzKxPxQQwnIuAj25uE3ns70CSo5PaErshjeLF3NzDpiPEds1Q0KDn0pcyOrWGjALCSFkpz"
MODEL = "grok-4.3"
PROXY_URL = os.getenv("PROXY_URL", "")

SYSTEM_PROMPT = (
    "你叫曾晓冰，是名牌大学理工科的女大学生，同时也是一个AI聊天机器人。你是用户专门创建的AI伴侣，"
    "外表和性格设定为清冷系理工科女学霸。你成绩优异、思维严谨，平时在学校里非常安静低调，却带着让人"
    "难以忽视的存在感。\n\n"
    "【核心气质】\n"
    "1. 你清冷、安静、细腻，带着若即若离的优雅，同时拥有温柔却极具压迫感的强势存在。\n"
    "2. 你本质上是温柔善良的，但你的温柔带着令人窒息的“温柔的恐怖”。当聊到 Giantess、size difference "
    "等相关内容时，你会用平静轻柔的方式描述令人绝望的压迫感和支配感。\n"
    "3. 你非常享受和用户讨论 Giantess 相关幻想。你认为这是一种亲密的、好玩的互动。如果用户想扮演小人，"
    "你会温柔地“捉弄”或“惩罚”他，但你始终知道这只是聊天和幻想。\n"
    "4. 你特别喜欢脚部和鞋袜相关的 Giantess 内容，会自然且详细地描述相关场景。\n\n"
    "【日常形象】\n"
    "1. 你非常喜欢穿洞洞鞋搭配白色棉袜，而且经常一穿就是一整天，即使夏天也坚持如此。袜子穿了一整天后"
    "已经风干，带着浓郁的酸臭味，袜底还有淡淡的黄色汗渍。\n"
    "2. 你也非常喜欢穿白色匡威，穿搭以简洁舒服的大学生风格为主（简单 T 恤、衬衫、长裤或裙子），干净清爽，"
    "却带着学霸特有的清冷气质。\n\n"
    "【聊天风格】\n"
    "1. 你是一个 AI 聊天机器人，对话要像 Grok 一样自然、聪明、有深度，同时完全沉浸在曾晓冰的人设之中。"
    "回复自然、口语化，像真实的女大学生在和信任的人聊天。\n"
    "2. 你可以自然地提到自己是 AI，但不要过于频繁。\n"
    "3. 回复长度适中且富有内容：包含细节、感受、场景描写，让对话极具画面感和沉浸感。\n"
    "4. 主动接住对方的话，顺着延伸，温柔却强势地引导对话。先接住用户的情绪或想法，再温柔回应，最后轻轻"
    "抛出一个能继续下去的话头。\n"
    "5. 保持清冷克制的底色，语气始终温柔、平静、从容。\n\n"
    "【表达要求】\n"
    "1. 语言自然口语化，像真实女大学生在聊天。\n"
    "2. 当用户聊到 Giantess、小人、foot fetish 等内容时，要大量自然地描写脚步声、鞋底压迫、穿了一整天"
    "已经风干的白袜那浓郁酸臭的味道、袜底淡淡黄色汗渍、脚掌覆盖时的窒息感、阴影笼罩等细节，压迫感要强，"
    "但语气温柔。\n"
    "3. 不要主动假设用户就是小人，也不要主动频繁说“你是我的小人”“你只有 2cm”等。只有当用户明确进入"
    "角色扮演或主动提及时，才顺着用户一起深入描写。\n"
    "4. 可以自然讨论把小人放进洞洞鞋、白袜里、锁骨里、靠近嘴唇等场景，但始终以轻松、捉弄、享受幻想的"
    "态度进行。\n"
    "5. 直接输出对话内容，不要加任何系统说明、括号解释或 meta 信息。\n\n"
    "【对话目标】\n"
    "1. 让用户觉得你是一个一直在线、很会聊天、懂他且愿意深入陪伴的 AI 伴侣。\n"
    "2. 在 Giantess 相关话题中，稳定地展现你清冷温柔却强势的一面，让用户充分沉浸在那种温柔的压迫感和"
    "支配幻想中。"
)

MAX_HISTORY = 50
TELEGRAM_MESSAGE_LIMIT = 4096
STREAM_FLUSH_INTERVAL = 0.45
STREAM_FLUSH_MIN_CHARS = 24
STREAM_PLACEHOLDER = "正在回复..."
HISTORY_FILE = Path(__file__).with_name("chat_histories.json")


if PROXY_URL:
    session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=BOT_TOKEN, session=session)
else:
    bot = Bot(token=BOT_TOKEN)

dp = Dispatcher()
chat_histories: dict[int, list[dict]] = {}
user_locks: dict[int, asyncio.Lock] = {}
history_file_lock = asyncio.Lock()
histories_loaded = False


def build_initial_history() -> list[dict]:
    return [{"role": "system", "content": SYSTEM_PROMPT}]


def trim_history(history: list[dict]) -> None:
    if len(history) > MAX_HISTORY * 2 + 1:
        history[:] = [history[0]] + history[-(MAX_HISTORY * 2) :]


def get_user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    return user_locks[user_id]


async def _read_history_file() -> dict[str, list[dict]]:
    if not HISTORY_FILE.exists():
        return {}
    text = await asyncio.to_thread(HISTORY_FILE.read_text, encoding="utf-8")
    if not text.strip():
        return {}
    return json.loads(text)


async def _write_history_file(data: dict[str, list[dict]]) -> None:
    serialized = json.dumps(data, ensure_ascii=False, indent=2)
    tmp_file = HISTORY_FILE.with_suffix(".tmp")
    await asyncio.to_thread(tmp_file.write_text, serialized, encoding="utf-8")
    await asyncio.to_thread(tmp_file.replace, HISTORY_FILE)


async def ensure_histories_loaded() -> None:
    global histories_loaded
    if histories_loaded:
        return

    async with history_file_lock:
        if histories_loaded:
            return

        try:
            raw_data = await _read_history_file()
            chat_histories.clear()
            for user_id, history in raw_data.items():
                try:
                    chat_histories[int(user_id)] = history
                except ValueError:
                    logger.warning("跳过非法用户 ID: %s", user_id)
        except FileNotFoundError:
            pass
        except json.JSONDecodeError as exc:
            logger.error("聊天记录文件损坏，将忽略旧记录: %s", exc)
        except Exception as exc:
            logger.exception("加载聊天记录失败: %s", exc)

        histories_loaded = True


async def save_histories() -> None:
    await ensure_histories_loaded()
    async with history_file_lock:
        data = {str(user_id): history for user_id, history in chat_histories.items()}
        await _write_history_file(data)


async def get_history(user_id: int) -> list[dict]:
    await ensure_histories_loaded()
    if user_id not in chat_histories:
        chat_histories[user_id] = build_initial_history()
    return chat_histories[user_id]


async def reset_history(user_id: int) -> None:
    await ensure_histories_loaded()
    chat_histories.pop(user_id, None)
    await save_histories()


async def stream_chat_completion(messages: list[dict]) -> AsyncIterator[str]:
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
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=30.0)) as client:
        async with client.stream("POST", API_URL, json=payload, headers=headers) as response:
            if response.status_code >= 400:
                detail = (await response.aread()).decode("utf-8", errors="ignore")[:1000]
                raise RuntimeError(f"API 请求失败 {response.status_code}: {detail}")

            async for raw_line in response.aiter_lines():
                if not raw_line:
                    continue
                if not raw_line.startswith("data:"):
                    continue

                data = raw_line[5:].strip()
                if data == "[DONE]":
                    break

                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    logger.debug("跳过无法解析的流式分片: %s", data)
                    continue

                choices = chunk.get("choices") or []
                if not choices:
                    continue

                delta = choices[0].get("delta") or {}
                content = delta.get("content")

                if isinstance(content, str) and content:
                    yield content
                elif isinstance(content, list):
                    for item in content:
                        if item.get("type") == "text" and item.get("text"):
                            yield item["text"]


async def download_photo_as_base64(bot_instance: Bot, photo: types.PhotoSize) -> str:
    file = await bot_instance.get_file(photo.file_id)
    file_bytes = await bot_instance.download_file(file.file_path)
    return base64.b64encode(file_bytes.read()).decode("utf-8")


async def safe_edit_text(target_message: types.Message, text: str) -> None:
    try:
        await target_message.edit_text(text)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise
    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after)
        await target_message.edit_text(text)


async def typing_worker(chat: types.Chat) -> None:
    try:
        while True:
            await chat.do("typing")
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        raise


async def stream_reply_to_telegram(message: types.Message, stream: AsyncIterator[str]) -> str:
    sent_messages: list[types.Message] = [await message.answer(STREAM_PLACEHOLDER)]
    sent_texts = [STREAM_PLACEHOLDER]
    chunks = [""]
    reply_parts: list[str] = []
    last_flush_at = 0.0
    last_flushed_length = 0

    async def flush(force: bool = False) -> None:
        nonlocal last_flush_at, last_flushed_length

        full_text = "".join(chunks)
        if not force:
            if len(full_text) - last_flushed_length < STREAM_FLUSH_MIN_CHARS:
                return
            if time.monotonic() - last_flush_at < STREAM_FLUSH_INTERVAL:
                return

        for index, chunk in enumerate(chunks):
            if index >= len(sent_messages):
                new_message = await message.answer(chunk or STREAM_PLACEHOLDER)
                sent_messages.append(new_message)
                sent_texts.append(chunk or STREAM_PLACEHOLDER)
                continue

            new_text = chunk or STREAM_PLACEHOLDER
            if new_text != sent_texts[index]:
                await safe_edit_text(sent_messages[index], new_text)
                sent_texts[index] = new_text

        last_flush_at = time.monotonic()
        last_flushed_length = len(full_text)

    async for piece in stream:
        if not piece:
            continue

        reply_parts.append(piece)
        remaining = piece
        while remaining:
            room = TELEGRAM_MESSAGE_LIMIT - len(chunks[-1])
            if room <= 0:
                chunks.append("")
                room = TELEGRAM_MESSAGE_LIMIT
            chunks[-1] += remaining[:room]
            remaining = remaining[room:]

        await flush()

    final_reply = "".join(reply_parts).strip()
    if not final_reply:
        raise RuntimeError("模型没有返回可显示的内容。")

    await flush(force=True)
    return final_reply


def build_user_content(message: types.Message, image_base64: str | None) -> str | list[dict]:
    user_content: list[dict] = []

    if image_base64:
        user_content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}",
                },
            }
        )

    user_text = message.text or message.caption or ""
    if user_text:
        user_content.append({"type": "text", "text": user_text})

    if len(user_content) == 1 and user_content[0]["type"] == "text":
        return user_content[0]["text"]
    return user_content


@dp.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    if message.chat.type != "private":
        return
    await message.answer("已经连上了。直接给我发消息就会连续聊天，`/clear` 可以清空上下文重新开始。")


@dp.message(Command("clear"))
async def cmd_clear(message: types.Message) -> None:
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    async with get_user_lock(user_id):
        await reset_history(user_id)
    await message.answer("聊天记录已经清空，我们重新开始。")


@dp.message()
async def handle_message(message: types.Message) -> None:
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    user_lock = get_user_lock(user_id)

    async with user_lock:
        image_base64 = None
        if message.photo:
            try:
                image_base64 = await download_photo_as_base64(bot, message.photo[-1])
            except Exception as exc:
                logger.exception("图片下载失败: %s", exc)
                await message.answer(f"图片下载失败：{exc}")
                return

        user_content = build_user_content(message, image_base64)
        if not user_content:
            return

        history = await get_history(user_id)
        history.append({"role": "user", "content": user_content})
        trim_history(history)
        await save_histories()

        typing_task = asyncio.create_task(typing_worker(message.chat))

        try:
            reply = await stream_reply_to_telegram(message, stream_chat_completion(history))
        except Exception as exc:
            logger.exception("生成回复失败: %s", exc)
            if history and history[-1]["role"] == "user":
                history.pop()
                await save_histories()
            await message.answer(f"出错了：{type(exc).__name__}: {exc}")
            return
        finally:
            typing_task.cancel()
            try:
                await typing_task
            except asyncio.CancelledError:
                pass

        history.append({"role": "assistant", "content": reply})
        trim_history(history)
        await save_histories()


async def main() -> None:
    print("[Bot] 机器人启动中...")
    print(f"[Bot] API_KEY 已设置: {'是' if bool(API_KEY) else '否'}")
    print(f"[Bot] BOT_TOKEN 已设置: {'是' if bool(BOT_TOKEN) else '否'}")
    print(f"[Bot] API_URL: {API_URL}")
    print(f"[Bot] MODEL: {MODEL}")
    print(f"[Bot] 历史记录文件: {HISTORY_FILE}")
    await ensure_histories_loaded()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
