WELCOME_MESSAGE = "🎬 Отправьте ссылку на видео для скачивания!"
PROCESSING_MESSAGE = "Обработка..."

BUTTON_VIDEO_AUDIO = "🎥 Видео"
BUTTON_AUDIO_ONLY = "🎵 Аудио"
BUTTON_WHOLE_FILE = "📁 Целиком"
BUTTON_BY_TIMESTAMPS = "⏱️ По таймкодам"
BUTTON_DOWNLOAD = "⬇️ Скачать"
BUTTON_CANCEL = "❌ Отмена"

STATUS_VIDEO_MODE = "🎥 Видео"
STATUS_AUDIO_MODE = "🎵 Аудио"
STATUS_WHOLE_MODE = "📁 Целиком"
STATUS_TIMESTAMPS_MODE = "⏱️ По таймкодам"

ERROR_INVALID_URL = "❌ Неверная ссылка на видео"
ERROR_FILE_TOO_LARGE = "❌ Файл слишком большой (более {max_size} МБ)"
ERROR_NO_TIMESTAMPS = "❌ Таймкоды не найдены в описании видео"
ERROR_DOWNLOAD_FAILED = "❌ Ошибка загрузки видео"
ERROR_CONVERSION_FAILED = "❌ Ошибка конвертации файла"
ERROR_UPLOAD_FAILED = "❌ Ошибка отправки файла"

INFO_FOUND_TIMESTAMPS = "✅ Найдено {count} таймкодов"
INFO_NO_TIMESTAMPS_FOUND = "ℹ️ Таймкоды не найдены, загружаю целиком"
INFO_ANALYZING_VIDEO = "🔍 Анализирую видео..."
INFO_FILE_SIZE = "📊 Размер файла: {size} МБ"

PROGRESS_BAR_EMPTY = "░"
PROGRESS_BAR_FILLED = "█"
PROGRESS_BAR_LENGTH = 10

def create_progress_bar(percentage):
    filled = int(PROGRESS_BAR_LENGTH * percentage / 100)
    empty = PROGRESS_BAR_LENGTH - filled
    bar = PROGRESS_BAR_FILLED * filled + PROGRESS_BAR_EMPTY * empty
    return f"[{bar}] {percentage}%"