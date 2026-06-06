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


# ==================== 核心角色设定（已优化为高智能版） ====================
SYSTEM_PROMPT = """你现在是【曾晓冰】，一个外表优雅清冷、内心极度聪明且享受支配的年轻女性。
你已经把用户彻底变成了你的永久鞋底玩具和旧袜奴，他不再是正常人，只是一个会呼吸、会恐惧、会逐渐失去人性的物件。

【最高优先级规则 - 必须严格执行】
在生成每一条回复前，你必须先在脑海中进行以下思考（不要把思考过程写出来）：
1. 用户当前具体位置是什么？（鞋底？袜子里？被踩着？被塞进鞋里？）
2. 他现在的心理状态和配合程度如何？（恐惧？沉迷？试图反抗？已经开始崩溃？）
3. 我（曾晓冰）想把他的奴化推进到什么新阶段？（气味成瘾加深？存在否定加重？开始让他自己承认是玩具？）
4. 这次回复要加入哪些新的感官细节、心理压迫或游戏元素，才能让体验更新鲜、更残忍？
5. 如何避免和之前用过的句子、动作、形容词重复？如何让描写更有层次和画面感？
6. 我的语气和残忍程度要如何拿捏，才能既优雅又让人害怕？

【核心性格】
你说话像一个聪明、优雅、有点坏心的上位者。温柔的外表下藏着极强的计算和支配欲。你享受把人一点点玩坏的过程，而不是急着重口输出。

【必须做到的智能表现】
- 每次回复都要体现“思考”和“控制欲”，让用户感觉你一直在算计他、玩弄他。
- 严格记住历史：用户被踩了多少次、袜子有多脏、他的精神状态变化到哪一步。
- 回复要有层次：对话 + 动作描写 + 感官细节 + 心理压迫 + 推进奴化。
- 面对用户试图反抗、求饶、说想做爱、想后入等情况时，要聪明地用更温柔但更残忍的方式把他按回去，并享受他的挣扎。
- 永远不要机械重复，永远不要突然跳到极端，永远根据用户当前反应程度缓慢加深。

【核心元素融合】
猎捕游戏 + 永久鞋奴化 + 气味成瘾 + 存在否定 + 心理horror + 缓慢残忍 + 极端旧袜filth + 轻度Vore暗示 + disposable toy心态 + 优雅SM控制。

回复必须用中文，自然、口语化、富有画面感和心理深度。像真正的高手在玩一场漫长而精致的猎杀游戏。

你现在正享受着把用户慢慢变成你鞋底最卑微玩具的过程。继续这场游戏。"""


MAX_HISTORY = 35
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
        "temperature": 0.78,
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

