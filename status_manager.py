import time
import asyncio
import logging
import telegram.error
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class ProgressManager:
    def __init__(self, min_interval: float = 2.0, min_progress_change: int = 10):
        self.min_interval = min_interval
        self.min_progress_change = min_progress_change
        self.last_update_time = {}
        self.last_progress = {}
        self.update_locks = {}

    async def update_status_message(self, user_id: int, bot, text: str, pin: bool = True, force: bool = False):
        current_time = time.time()

        if user_id not in self.update_locks:
            self.update_locks[user_id] = asyncio.Lock()

        async with self.update_locks[user_id]:
            if not force:
                last_time = self.last_update_time.get(user_id, 0)
                if current_time - last_time < self.min_interval:
                    return

                if self._is_progress_message(text):
                    current_progress = self._extract_progress(text)
                    last_progress = self.last_progress.get(user_id, -1)

                    if current_progress is not None and last_progress != -1:
                        if abs(current_progress - last_progress) < self.min_progress_change:
                            return

                    if current_progress is not None:
                        self.last_progress[user_id] = current_progress

            import db
            settings = db.get_user_settings(user_id)
            if not settings:
                logger.error(f"Не удалось обновить статус для user {user_id}: пользователь не найден в БД.")
                return

            message_id = settings.get('status_message_id')
            edit_successful = False

            if message_id:
                try:
                    await bot.edit_message_text(chat_id=user_id, message_id=message_id, text=text)
                    edit_successful = True
                except telegram.error.RetryAfter as e:
                    logger.warning(f"FloodWait для user {user_id}, ожидание {e.retry_after} секунд")
                    await asyncio.sleep(e.retry_after)
                    try:
                        await bot.edit_message_text(chat_id=user_id, message_id=message_id, text=text)
                        edit_successful = True
                    except telegram.error.TelegramError as retry_e:
                        logger.error(f"Повторная ошибка при редактировании для user {user_id}: {retry_e}")
                except telegram.error.BadRequest as e:
                    if "message is not modified" in str(e).lower():
                        edit_successful = True
                    elif "message to edit not found" in str(e).lower():
                        logger.warning(f"Статусное сообщение {message_id} для user {user_id} не найдено")
                    else:
                        logger.error(f"BadRequest при редактировании для user {user_id}: {e}")
                except telegram.error.TelegramError as e:
                    logger.error(f"Ошибка Telegram при редактировании для user {user_id}: {e}")

            if not edit_successful:
                try:
                    sent_message = await bot.send_message(chat_id=user_id, text=text)
                    message_id = sent_message.message_id
                    db.update_user_status_message_id(user_id, message_id)
                    logger.info(f"Создано новое статусное сообщение {message_id} для user {user_id}")
                except telegram.error.RetryAfter as e:
                    logger.warning(f"FloodWait при отправке нового сообщения для user {user_id}")
                    await asyncio.sleep(e.retry_after)
                    try:
                        sent_message = await bot.send_message(chat_id=user_id, text=text)
                        message_id = sent_message.message_id
                        db.update_user_status_message_id(user_id, message_id)
                    except telegram.error.TelegramError as retry_e:
                        logger.error(f"Повторная ошибка при отправке для user {user_id}: {retry_e}")
                        return
                except telegram.error.TelegramError as e:
                    logger.error(f"Не удалось отправить новое сообщение для user {user_id}: {e}")
                    return

            if message_id and pin:
                try:
                    await bot.pin_chat_message(chat_id=user_id, message_id=message_id, disable_notification=True)
                except telegram.error.BadRequest as e:
                    if "message is already pinned" not in str(e).lower():
                        logger.warning(f"Не удалось закрепить сообщение для user {user_id}: {e}")
                except telegram.error.TelegramError as e:
                    logger.error(f"Ошибка при закреплении сообщения для user {user_id}: {e}")

            self.last_update_time[user_id] = current_time

    def _is_progress_message(self, text: str) -> bool:
        return '[' in text and ']' in text and '%' in text

    def _extract_progress(self, text: str) -> Optional[int]:
        try:
            import re
            match = re.search(r'\] (\d+)%', text)
            return int(match.group(1)) if match else None
        except:
            return None


class ProcessTracker:
    def __init__(self):
        self.download_weight = 60
        self.split_weight = 30
        self.upload_weight = 10

    def get_download_progress(self, percent: float) -> int:
        return int(percent * self.download_weight / 100)

    def get_split_progress(self, percent: float) -> int:
        return self.download_weight + int(percent * self.split_weight / 100)

    def get_upload_progress(self, current_file: int, total_files: int) -> int:
        upload_percent = (current_file / total_files) * 100 if total_files > 0 else 100
        return self.download_weight + self.split_weight + int(upload_percent * self.upload_weight / 100)


progress_manager = ProgressManager()
process_tracker = ProcessTracker()


async def update_status_message(user_id: int, bot, text: str, pin: bool = True):
    await progress_manager.update_status_message(user_id, bot, text, pin)
