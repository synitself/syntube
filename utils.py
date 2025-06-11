import re
import unicodedata
from pathlib import Path
from typing import Optional


def sanitize_filename(filename: str) -> str:
    filename = str(filename).replace("/", "-").replace("\\", "-")
    try:
        filename = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('ascii')
    except (TypeError, ValueError):
        pass
    filename = re.sub(r'[^\w\s.\-_()]', '', filename).strip()
    filename = re.sub(r'\s+', ' ', filename)
    if not filename:
        filename = "downloaded_track"
    return filename[:200]


def format_duration(seconds: int) -> str:
    """Форматирует длительность в человеко-читаемый вид"""
    if seconds < 60:
        return f"{seconds}с"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"


def format_file_size(size_bytes: int) -> str:
    """Форматирует размер файла в человеко-читаемый вид"""
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} КБ"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} МБ"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} ГБ"


def create_temp_dir(user_id: int, base_dir: str = "temp") -> Path:
    """Создает временную директорию для пользователя"""
    temp_dir = Path(base_dir) / f"user_{user_id}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def cleanup_temp_dir(temp_dir: Path):
    """Очищает временную директорию"""
    try:
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"Ошибка очистки временной директории {temp_dir}: {e}")


def validate_url(url: str) -> bool:
    """Проверяет, является ли строка валидным URL"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    return url_pattern.match(url) is not None


def extract_video_id(url: str) -> Optional[str]:
    """Извлекает ID видео из URL (для YouTube)"""
    youtube_patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/v/([a-zA-Z0-9_-]{11})'
    ]

    for pattern in youtube_patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def get_platform_name(url: str) -> str:
    """Определяет название платформы по URL"""
    domain_map = {
        'youtube.com': 'YouTube',
        'youtu.be': 'YouTube',
        'vk.com': 'VK Video',
        'rutube.ru': 'Rutube',
        'ok.ru': 'Одноклассники',
        'dailymotion.com': 'Dailymotion',
        'vimeo.com': 'Vimeo',
        'tiktok.com': 'TikTok',
        'instagram.com': 'Instagram',
        'facebook.com': 'Facebook',
        'twitter.com': 'Twitter',
        'x.com': 'X (Twitter)'
    }

    for domain, platform in domain_map.items():
        if domain in url.lower():
            return platform

    return "Неизвестная платформа"


def escape_markdown(text: str) -> str:
    """Экранирует специальные символы для Markdown"""
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']

    for char in escape_chars:
        text = text.replace(char, f'\\{char}')

    return text


def truncate_text(text: str, max_length: int = 50) -> str:
    """Обрезает текст до максимальной длины с добавлением многоточия"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def parse_time_string(time_str: str) -> Optional[int]:
    """Парсит строку времени в секунды (например, '1:23' -> 83)"""
    try:
        # Удаляем лишние символы
        time_str = time_str.strip()

        # Поддерживаем форматы: MM:SS, H:MM:SS, SS
        parts = time_str.split(':')

        if len(parts) == 1:  # Только секунды
            return int(parts[0])
        elif len(parts) == 2:  # Минуты:секунды
            minutes, seconds = map(int, parts)
            return minutes * 60 + seconds
        elif len(parts) == 3:  # Часы:минуты:секунды
            hours, minutes, seconds = map(int, parts)
            return hours * 3600 + minutes * 60 + seconds
        else:
            return None
    except (ValueError, TypeError):
        return None


def seconds_to_time_string(seconds: int) -> str:
    """Конвертирует секунды в строку времени"""
    if seconds < 0:
        return "0:00"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"