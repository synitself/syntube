# settings.py

# Основные сообщения
WELCOME_MESSAGE = "🎬 Отправьте ссылку на видео для скачивания!"
# Упрощенное сообщение для прогресса. Мы будем использовать только прогресс-бар.
PROCESSING_MESSAGE = "Обработка..."

# Старые сообщения о прогрессе (можно удалить или закомментировать)
# DOWNLOAD_PROGRESS = "📥 Загружаю: {progress}%"
# CONVERSION_PROGRESS = "🔄 Конвертирую: {progress}%"
# SPLITTING_PROGRESS = "✂️ Разделяю на сегменты: {progress}%"
# UPLOAD_PROGRESS = "📤 Отправляю файлы..."

# Кнопки меню
BUTTON_VIDEO_AUDIO = "🎥 Видео"
BUTTON_AUDIO_ONLY = "🎵 Аудио"
BUTTON_WHOLE_FILE = "📁 Целиком"
BUTTON_BY_TIMESTAMPS = "⏱️ По таймкодам"
BUTTON_DOWNLOAD = "⬇️ Скачать"
BUTTON_CANCEL = "❌ Отмена"

# Статусы режимов
STATUS_VIDEO_MODE = "🎥 Видео"
STATUS_AUDIO_MODE = "🎵 Аудио"
STATUS_WHOLE_MODE = "📁 Целиком"
STATUS_TIMESTAMPS_MODE = "⏱️ По таймкодам"

# Сообщения об ошибках
ERROR_INVALID_URL = "❌ Неверная ссылка на видео"
ERROR_FILE_TOO_LARGE = "❌ Файл слишком большой (более {max_size} МБ)"
ERROR_NO_TIMESTAMPS = "❌ Таймкоды не найдены в описании видео"
ERROR_DOWNLOAD_FAILED = "❌ Ошибка загрузки видео"
ERROR_CONVERSION_FAILED = "❌ Ошибка конвертации файла"
ERROR_UPLOAD_FAILED = "❌ Ошибка отправки файла"

# Успешные операции
# SUCCESS_DOWNLOAD_COMPLETE = "✅ Загрузка завершена!" # Больше не используется
# SUCCESS_FILES_SENT = "✅ Файлы отправлены!" # Больше не используется

# Информационные сообщения
INFO_FOUND_TIMESTAMPS = "✅ Найдено {count} таймкодов"
INFO_NO_TIMESTAMPS_FOUND = "ℹ️ Таймкоды не найдены, загружаю целиком"
INFO_ANALYZING_VIDEO = "🔍 Анализирую видео..."
INFO_FILE_SIZE = "📊 Размер файла: {size} МБ"

# Форматы прогресс-бара
PROGRESS_BAR_EMPTY = "░"
PROGRESS_BAR_FILLED = "█"
PROGRESS_BAR_LENGTH = 10

def create_progress_bar(percentage):
    """Создает прогресс-бар"""
    filled = int(PROGRESS_BAR_LENGTH * percentage / 100)
    empty = PROGRESS_BAR_LENGTH - filled
    bar = PROGRESS_BAR_FILLED * filled + PROGRESS_BAR_EMPTY * empty
    return f"[{bar}] {percentage}%"