import logging
import telegram.error
from telegram import Bot
import db

logger = logging.getLogger(__name__)

async def update_status_message(user_id: int, bot: Bot, text: str, pin: bool = True):
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
        except telegram.error.BadRequest as e:
            if "message is not modified" in str(e).lower():
                edit_successful = True
            elif "message to edit not found" in str(e).lower():
                logger.warning(f"Статусное сообщение {message_id} для user {user_id} не найдено, будет создано новое.")
            else:
                logger.error(f"Ошибка BadRequest при редактировании статуса для user {user_id}: {e}")
        except telegram.error.TelegramError as e:
            logger.error(f"Ошибка Telegram при редактировании статуса для user {user_id}: {e}")

    if not edit_successful:
        try:
            sent_message = await bot.send_message(chat_id=user_id, text=text)
            message_id = sent_message.message_id
            db.update_user_status_message_id(user_id, message_id)
            logger.info(f"Создано новое статусное сообщение {message_id} для user {user_id}.")
        except telegram.error.TelegramError as e:
            logger.error(f"Не удалось отправить новое статусное сообщение для user {user_id}: {e}")
            return

    if message_id and pin:
        try:
            await bot.pin_chat_message(chat_id=user_id, message_id=message_id, disable_notification=True)
        except telegram.error.BadRequest as e:
            if "message is already pinned" not in str(e).lower() and "chat not modified" not in str(e).lower():
                 logger.warning(f"Не удалось закрепить сообщение {message_id} для user {user_id}: {e}")
        except telegram.error.TelegramError as e:
            logger.error(f"Ошибка Telegram при закреплении сообщения для user {user_id}: {e}")