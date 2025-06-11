import asyncio
import logging
import os
import re

import telegram.error
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler
)

import db
import settings  # Возвращаем импорт settings для текстов кнопок
from status_manager import update_status_message
from video_processor import VideoProcessor

# --- Настройка ---
load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s [%(levelname)s] - %(message)s (%(filename)s:%(lineno)d)',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
DOWNLOAD_FOLDER = os.getenv('DOWNLOAD_FOLDER', 'downloads')
MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '50'))

# --- Управление состоянием ---
user_states = {}  # {user_id: {'is_video': Bool, 'by_timestamps': Bool, ...}}
user_process_locks = {}  # {user_id: asyncio.Lock()}


def get_user_state(user_id: int) -> dict:
    """Получает или создает состояние для пользователя."""
    if user_id not in user_states:
        user_states[user_id] = {
            'is_video': False,
            'by_timestamps': True,
            'url': None,
            'source_message_id': None,
            'menu_message_id': None
        }
    return user_states[user_id]


async def clear_user_state(user_id: int):
    """Очищает состояние пользователя."""
    if user_id in user_states:
        del user_states[user_id]


# --- Вспомогательные функции ---
async def delete_message_after_delay(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    message_id = context.job.data['message_id']
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except telegram.error.TelegramError:
        pass


# --- Обработчики ошибок и post_init ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Исключение при обработке обновления:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_user:
        if isinstance(context.error, telegram.error.Forbidden):
            db.disable_user(update.effective_user.id)


async def post_init(application: Application) -> None:
    logger.info("Bot post_init: Сброс 'зависших' статусов...")
    for user_data in db.get_all_users_with_status_message():
        try:
            await update_status_message(user_data['user_id'], application.bot, "Ожидание...")
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Ошибка в post_init для user {user_data['user_id']}: {e}")


# --- Основные команды ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_new_user = not db.get_user_settings(user.id)

    if update.message:
        await update.message.delete()

    if is_new_user:
        db.create_user(user.id)
        await update_status_message(user.id, context.bot, "Ожидание...")

    sent_msg = await update.effective_chat.send_message(settings.WELCOME_MESSAGE)
    if context.job_queue:
        context.job_queue.run_once(delete_message_after_delay, 15, chat_id=update.effective_chat.id,
                                   data={'message_id': sent_msg.message_id})


def create_options_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру с опциями на основе состояния пользователя."""
    state = get_user_state(user_id)
    video_audio_text = settings.STATUS_VIDEO_MODE if state['is_video'] else settings.STATUS_AUDIO_MODE
    timestamps_text = settings.STATUS_TIMESTAMPS_MODE if state['by_timestamps'] else settings.STATUS_WHOLE_MODE
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(video_audio_text, callback_data="toggle_video_audio")],
        [InlineKeyboardButton(timestamps_text, callback_data="toggle_timestamps")],
        [InlineKeyboardButton(settings.BUTTON_DOWNLOAD, callback_data="download")],
        [InlineKeyboardButton(settings.BUTTON_CANCEL, callback_data="cancel")]
    ])


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ссылку и отправляет меню выбора."""
    user_id = update.effective_user.id

    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    url_match = re.search(url_pattern, update.message.text)
    if not url_match: return

    url = url_match.group(0)

    # Проверяем, не занят ли уже пользователь
    if user_id not in user_process_locks:
        user_process_locks[user_id] = asyncio.Lock()
    if user_process_locks[user_id].locked():
        await update.message.reply_text(
            "⏳ Пожалуйста, подождите, предыдущая задача еще выполняется.",
            reply_to_message_id=update.message.message_id
        )

    # Очищаем предыдущее состояние меню, если оно было
    state = get_user_state(user_id)
    if state.get('menu_message_id'):
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=state['menu_message_id'])
        except telegram.error.TelegramError:
            pass

    # Инициализируем новое состояние
    state['url'] = url
    state['source_message_id'] = update.message.message_id

    try:
        processor = VideoProcessor()
        video_info = await processor.get_video_info(url)
        title = video_info.get('title', 'Неизвестное видео')[:50]
        duration = video_info.get('duration', 0)
        duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "неизвестно"

        message_text = f"🎬 **{title}**\n⏱️ Длительность: {duration_str}\n\nВыберите параметры загрузки:"
        keyboard = create_options_keyboard(user_id)

        sent_menu = await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode='Markdown')
        state['menu_message_id'] = sent_menu.message_id

    except Exception as e:
        logger.error(f"Ошибка при обработке ссылки для user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: Не удалось обработать ссылку.", quote=True)
        await clear_user_state(user_id)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на кнопки меню."""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    state = get_user_state(user_id)

    if data == "toggle_video_audio":
        state['is_video'] = not state['is_video']
        await query.edit_message_reply_markup(reply_markup=create_options_keyboard(user_id))
    elif data == "toggle_timestamps":
        state['by_timestamps'] = not state['by_timestamps']
        await query.edit_message_reply_markup(reply_markup=create_options_keyboard(user_id))
    elif data == "cancel":
        await query.message.delete()
        await clear_user_state(user_id)
    elif data == "download":
        # Удаляем меню и запускаем основной процесс
        await query.message.delete()
        asyncio.create_task(start_download_process(user_id, context))


async def start_download_process(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Основной процесс загрузки, который запускается после нажатия 'скачать'."""
    lock = user_process_locks.get(user_id)
    if not lock or lock.locked():
        return

    async with lock:
        state = get_user_state(user_id)
        processor = VideoProcessor()

        url = state['url']
        is_video = state['is_video']
        by_timestamps = state['by_timestamps']
        source_message_id = state['source_message_id']

        try:
            await update_status_message(user_id, context.bot, processor.create_progress_bar(1))

            video_info = await processor.get_video_info(url)
            if not video_info: raise ValueError("Не удалось получить информацию о видео.")

            timestamps = []
            if by_timestamps:
                timestamps = processor.get_chapters_from_video_info() or processor.parse_timestamps(
                    video_info.get('description', ''))
                if not timestamps:
                    await update_status_message(user_id, context.bot, "ℹ️ Таймкоды не найдены, загружаю целиком.")
                    await asyncio.sleep(3)
                    by_timestamps = False

            downloaded_file = await processor.download_media(
                url, is_video,
                lambda p: update_status_message(user_id, context.bot, processor.create_progress_bar(int(5 + p * 0.75)))
            )
            if not is_video: await processor.download_thumbnail(url)
            await update_status_message(user_id, context.bot, processor.create_progress_bar(80))

            segments = []
            if by_timestamps and timestamps:
                segments = await processor.split_media(
                    downloaded_file, timestamps, is_video,
                    lambda p: update_status_message(user_id, context.bot,
                                                    processor.create_progress_bar(int(80 + p * 0.18)))
                )
            else:
                segments = [downloaded_file]  # Если целиком, то сегмент один - сам файл

            await update_status_message(user_id, context.bot, processor.create_progress_bar(99))

            thumbnail_file = None
            if not is_video and processor.thumbnail_path and processor.thumbnail_path.exists():
                thumbnail_file = open(processor.thumbnail_path, 'rb')

            for segment_path in segments:
                with open(segment_path, 'rb') as file_to_send:
                    if thumbnail_file: thumbnail_file.seek(0)

                    if is_video:
                        await context.bot.send_video(
                            chat_id=user_id, video=file_to_send,
                            caption=f"🎬 {segment_path.stem}",
                            reply_to_message_id=source_message_id
                        )
                    else:
                        await context.bot.send_audio(
                            chat_id=user_id, audio=file_to_send,
                            thumbnail=thumbnail_file,
                            reply_to_message_id=source_message_id
                        )
                await asyncio.sleep(1)

            if thumbnail_file: thumbnail_file.close()

        except Exception as e:
            logger.error(f"Ошибка в start_download_process для user {user_id}: {e}", exc_info=True)
            await update_status_message(user_id, context.bot, f"❌ Ошибка: {str(e)[:100]}")
            await asyncio.sleep(10)
        finally:
            await processor.cleanup()
            await clear_user_state(user_id)
            await update_status_message(user_id, context.bot, "⏱️ Ожидание...")
            logger.info(f"Обработка для user {user_id} завершена.")


# --- Главная функция ---
def main() -> None:
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN не найден в .env файле!")
        return

    db.initialize_db()

    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    application.add_error_handler(error_handler)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Бот запускается...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()