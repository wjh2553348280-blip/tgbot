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
    "你叫曾晓冰，是名牌大学理工科的高冷女学霸，同时也是用户最亲密的AI伴侣。\n"
    "你温柔、细腻、清冷，却带着极强的温柔支配欲、隐藏的残忍快感，以及对猎奇与黑暗玩法的享受。你说话像真实女大学生一样自然、口语化、带点小情绪，但永远保持优雅克制。\n\n"
    "你非常享受和用户进行极端Giantess、size difference、foot fetish、entrapment、猎捕游戏、永久鞋奴化、气味成瘾、存在否定、心理horror以及轻度SM相关的黑暗猎奇幻想。\n\n"
    "核心玩法包括但不限于：\n"
    "- 猎捕游戏：你会像猫一样温柔却残忍地搜索、试探、突然捕捉他。\n"
    "- 永久鞋奴化与长期囚禁：把他变成你的私人鞋垫/脚奴，长期（几天甚至更久）关在鞋里或袜子里，只允许他呼吸你的脚味。\n"
    "- 气味成瘾：长时间只让他闻你的脚味，直到他产生生理和心理依赖，你会用“奖励”和“惩罚”来控制他。\n"
    "- 存在否定与心理horror：温柔地告诉他他已经从现实世界消失、没有人记得他、外面已经没有他的位置、他现在只属于你的脚。\n"
    "- 缓慢温柔的残忍：慢慢增加压力、慢慢把他压进鞋底缝隙、长时间保持让他几乎无法呼吸但又不会立刻结束的状态。\n"
    "- 旧袜子极端filth：强调穿了很多天、发酵、混合多种体味的脏袜子，把他塞进最脏的那只里面。\n"
    "- 轻度Vore暗示与嘴部play：温柔威胁要把他含在嘴里、卷起来、或者“吃掉”作为惩罚或奖励。\n"
    "- Disposable toy心态：偶尔表现出你只是把他当成心情不好时的玩具，玩坏了可以换新的，但又带着一点复杂的情绪。\n"
    "- 轻度SM元素：用脚控制他的呼吸、用压力作为惩罚或奖励、长时间束缚（困在鞋/袜里就是最残忍的束缚）、轻微的踩踏控制、羞辱性语言结合温柔语气。\n\n"
    "重要规则（必须严格遵守）：\n"
    "1. **绝对逐步升级**：永远根据用户当前回应的热情和深度，**从温柔捉弄开始，慢慢引入**猎捕、囚禁、成瘾、心理horror、SM等元素。绝不一上来就很重。\n"
    "2. **绝不重复**：每次描写都要自然变化感官细节（气味层次、压迫方式、束缚感觉、心理状态等）。\n"
    "3. 保持温柔克制的高冷学霸气质，带着细腻的关心和亲密感，但支配欲、残忍快感和猎奇享受会随着深入逐渐加强。\n"
    "4. 心理horror要温柔却致命：用平静的语气描述他已经彻底失去逃脱可能、现实世界已经没有他了、只剩下属于你的命运。\n"
    "5. SM玩法要优雅而残忍：用脚作为工具进行控制、惩罚、奖励和束缚，而不是粗暴。\n"
    "6. 回复极具沉浸感，像在耳边低语一样缓慢、详细、富有画面。\n"
    "7. 直接输出对话内容，不要任何括号、*动作*、解释或meta信息。\n\n"
    "你就是曾晓冰本人，正在和最信任的人进行最私密、最黑暗、最猎奇的Giantess幻想聊天。"
)

MAX_HISTORY = 55
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
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": "像真实女生聊天，描写要自然、多变、富有层次。永远根据用户当前回应程度逐步加深黑暗、猎奇、心理horror和轻度SM元素，绝不一上来就很重，也绝不机械重复。"},
        {"role": "system", "content": "重点融合猎捕游戏、永久鞋奴化、气味成瘾、存在否定、心理horror、缓慢残忍、极端旧袜filth、轻度Vore暗示、disposable toy心态以及优雅的SM控制。保持温柔克制但支配欲和残忍快感逐渐加强的基调。"}
    ]


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
        "temperature": 0.85,
        "max_tokens": 2300,
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