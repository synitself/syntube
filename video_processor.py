import os
import re
import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any, Callable
import yt_dlp
from PIL import Image
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
import logging
import unicodedata

logger = logging.getLogger(__name__)


class VideoProcessor:
    def __init__(self, temp_dir: str = None):
        unique_id = os.urandom(4).hex()
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / f"video_bot_{unique_id}"
        self.video_info = None
        self.thumbnail_path = None
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        self.temp_dir.mkdir(exist_ok=True, parents=True)

    def create_progress_bar(self, percentage: int, length: int = 10) -> str:
        percentage = max(0, min(100, percentage))
        filled_length = int(length * percentage // 100)
        bar = '█' * filled_length + '░' * (length - filled_length)
        return f"[{bar}] {percentage}%"

    def normalize_unicode_text(self, text: str) -> str:
        try:
            normalized = unicodedata.normalize('NFC', text)
            return normalized
        except Exception as e:
            logger.warning(f"Ошибка нормализации Unicode: {e}")
            return text

    def sanitize_metadata_text(self, text: str, max_length: int = 100) -> str:
        if not text:
            return "Unknown"

        text = self.normalize_unicode_text(text)
        text = text.strip()

        if len(text) > max_length:
            text = text[:max_length - 3] + "..."

        return text if text else "Unknown"

    async def get_video_info(self, video_url: str) -> Dict[str, Any]:
        ydl_opts = {'quiet': True, 'no_warnings': True, 'extractflat': 'discard_in_playlist'}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await self.loop.run_in_executor(None, lambda: ydl.extract_info(video_url, download=False))
                self.video_info = info
                return info
        except Exception as e:
            raise Exception(f"Ошибка получения информации о видео: {str(e)}") from e

    def parse_timestamps(self, description: str) -> List[Tuple[int, str]]:
        timestamps = []
        patterns = [
            r'(?:^|\n)\s*((?:\d{1,2}:)?(?:[0-5]?\d):(?:[0-5]\d))\s+(.+?)(?=\n|$)',
            r'(?:^|\n)\s*\[((?:\d{1,2}:)?(?:[0-5]?\d):(?:[0-5]\d))\]\s+(.+?)(?=\n|$)',
            r'(?:^|\n)\s*((?:\d{1,2}:)?(?:[0-5]?\d):(?:[0-5]\d))\s*[-—–]\s*(.+?)(?=\n|$)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, description, re.MULTILINE | re.IGNORECASE)
            if matches:
                for time_str, title in matches:
                    parts = list(map(int, time_str.split(':')))
                    seconds = 0
                    if len(parts) == 3:
                        seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
                    elif len(parts) == 2:
                        seconds = parts[0] * 60 + parts[1]
                    else:
                        seconds = parts[0]
                    clean_title = self.clean_track_name(title.strip())
                    if clean_title: timestamps.append((seconds, clean_title))
                break
        timestamps.sort(key=lambda x: x[0])
        return timestamps

    def get_chapters_from_video_info(self) -> List[Tuple[int, str]]:
        if not self.video_info: return []
        chapters = self.video_info.get('chapters', [])
        timestamps = []
        for chapter in chapters:
            start_time = chapter.get('start_time', 0)
            title = chapter.get('title', f'Часть {len(timestamps) + 1}')
            clean_title = self.clean_track_name(title)
            timestamps.append((int(start_time), clean_title))
        return timestamps

    def clean_track_name(self, name: str) -> str:
        if not name:
            return 'Unnamed Track'

        name = self.normalize_unicode_text(name)
        cleaned = re.sub(r'[<>:"/\\|?*]', '', name)
        cleaned = re.sub(r'^\d+[.\s]*', '', cleaned)
        cleaned = cleaned.strip()

        if len(cleaned) > 80:
            cleaned = cleaned[:80] + "..."

        return cleaned if cleaned else 'Unnamed Track'

    def sanitize_filename(self, filename: str) -> str:
        if not filename:
            return "unknown_file"

        filename = self.normalize_unicode_text(filename)
        sanitized = re.sub(r'[<>:"/\\|?*]', '', filename).strip()

        if len(sanitized) > 100:
            sanitized = sanitized[:100]

        return sanitized if sanitized else "unknown_file"

    def _process_thumbnail(self, image_path: Path) -> Path:
        try:
            processed_path = image_path.with_suffix('.jpg')
            with Image.open(image_path) as img:
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.thumbnail((320, 320))
                img.save(processed_path, 'jpeg', quality=85, optimize=True)
            if image_path != processed_path and image_path.exists():
                image_path.unlink()
            return processed_path
        except Exception as e:
            logger.error(f"Не удалось обработать обложку {image_path}: {e}")
            return image_path

    def _blocking_download_thumbnail(self, best_thumbnail):
        import requests
        response = requests.get(best_thumbnail['url'], stream=True, timeout=30)
        response.raise_for_status()
        file_ext, content_type = '.jpg', response.headers.get('content-type')
        if content_type:
            if 'webp' in content_type:
                file_ext = '.webp'
            elif 'png' in content_type:
                file_ext = '.png'
        video_id = self.video_info.get('id', os.urandom(4).hex())
        original_thumb_path = self.temp_dir / f"thumbnail_{video_id}{file_ext}"
        with open(original_thumb_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
        self.thumbnail_path = self._process_thumbnail(original_thumb_path)
        return self.thumbnail_path

    async def download_thumbnail(self, video_url: str) -> Optional[Path]:
        try:
            if not self.video_info: await self.get_video_info(video_url)
            thumbnails = self.video_info.get('thumbnails', [])
            if not thumbnails: return None
            thumbnails.sort(key=lambda x: x.get('width', 0) * x.get('height', 0), reverse=True)
            return await self.loop.run_in_executor(None, self._blocking_download_thumbnail, thumbnails[0])
        except Exception as e:
            logger.warning(f"Ошибка загрузки обложки: {e}")
            return None

    async def download_media(self, video_url: str, is_video: bool = True,
                             progress_callback: Optional[Callable[[float], None]] = None) -> Path:
        def progress_hook(d):
            if d['status'] == 'downloading' and progress_callback:
                percent_str = d.get('_percent_str', '0%').strip().replace('%', '')
                try:
                    percent = float(percent_str)
                    asyncio.run_coroutine_threadsafe(progress_callback(percent), self.loop)
                except (ValueError, TypeError):
                    pass

        format_selector = 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' if is_video else 'bestaudio[ext=m4a]/bestaudio/best'
        safe_title = self.sanitize_filename(self.video_info['title'])
        output_template = self.temp_dir / f'{safe_title}.%(ext)s'

        ydl_opts = {
            'format': format_selector,
            'outtmpl': str(output_template),
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [progress_hook]
        }

        if not is_video:
            ydl_opts['postprocessors'] = [
                {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]

        await self.loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([video_url]))

        ext = 'mp4' if is_video else 'mp3'
        expected_file = self.temp_dir / f"{safe_title}.{ext}"
        if expected_file.exists(): return expected_file

        search_ext = ['.mp4', '.mkv', '.webm'] if is_video else ['.mp3', '.m4a', '.opus']
        for file_path in self.temp_dir.glob(f"{safe_title}.*"):
            if file_path.suffix.lower() in search_ext: return file_path

        raise FileNotFoundError(f"Загруженный файл не найден: {expected_file}")

    def _blocking_add_metadata(self, file_path: Path, title: str, artist: str):
        try:
            title = self.sanitize_metadata_text(title, 100)
            artist = self.sanitize_metadata_text(artist, 100)

            logger.info(f"Добавление метаданных в {file_path.name}: title='{title}', artist='{artist}'")

            audio = MP3(str(file_path))

            if audio.tags is None:
                audio.add_tags()
                logger.info(f"Добавлены новые теги для {file_path.name}")

            audio.tags.delall('TIT2')
            audio.tags.add(TIT2(encoding=3, text=title))

            audio.tags.delall('TPE1')
            audio.tags.add(TPE1(encoding=3, text=artist))

            audio.tags.delall('APIC')
            if self.thumbnail_path and self.thumbnail_path.exists():
                try:
                    with open(self.thumbnail_path, 'rb') as art:
                        audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=art.read()))
                except Exception as thumb_e:
                    logger.warning(f"Ошибка добавления обложки в {file_path.name}: {thumb_e}")

            audio.save(v2_version=3)
            logger.info(f"Метаданные успешно сохранены для {file_path.name}")

        except Exception as e:
            logger.error(f"КРИТИЧЕСКАЯ ОШИБКА при добавлении метаданных в {file_path.name}: {e}", exc_info=True)
            raise

    async def add_metadata_to_audio(self, file_path: Path, title: str, artist: str):
        await self.loop.run_in_executor(None, self._blocking_add_metadata, file_path, title, artist)

    async def split_media_ffmpeg(self, file_path: Path, timestamps: List[Tuple[int, str]], is_video: bool,
                                 progress_callback: Optional[Callable[[int], None]] = None) -> List[Path]:
        segments = []
        total_duration = self.video_info.get('duration')
        file_extension = file_path.suffix

        for i, (start_time, title) in enumerate(timestamps):
            end_time = timestamps[i + 1][0] if i + 1 < len(timestamps) else total_duration

            if end_time is None:
                logger.warning(f"Не удалось определить время окончания для последнего сегмента '{title}', пропускаем.")
                continue

            clean_title = self.sanitize_filename(title)
            segment_path = self.temp_dir / f"{i + 1:02d}. {clean_title}{file_extension}"

            ffmpeg_cmd = [
                'ffmpeg', '-hide_banner', '-loglevel', 'error',
                '-i', str(file_path),
                '-ss', str(start_time),
                '-to', str(end_time),
                '-c', 'copy',
                '-y',
                str(segment_path)
            ]

            process = await asyncio.create_subprocess_exec(*ffmpeg_cmd)
            await process.communicate()

            if process.returncode == 0:
                segments.append(segment_path)
            else:
                logger.error(f"Ошибка FFMPEG при создании сегмента '{segment_path.name}'.")

            if progress_callback:
                progress_percent = int((i + 1) / len(timestamps) * 100)
                await progress_callback(progress_percent)

        if not is_video:
            video_title = self.video_info.get('title', 'Unknown Album')
            for i, segment_path in enumerate(segments):
                try:
                    track_title = timestamps[i][1] if i < len(timestamps) else f"Track {i + 1}"
                    await self.add_metadata_to_audio(
                        file_path=segment_path,
                        title=track_title,
                        artist=video_title
                    )
                except Exception as metadata_e:
                    logger.error(f"Ошибка добавления метаданных для сегмента {segment_path.name}: {metadata_e}")

        return segments

    async def split_media(self, file_path: Path, timestamps: List[Tuple[int, str]], is_video: bool = True,
                          progress_callback: Optional[Callable[[int], None]] = None) -> List[Path]:
        return await self.split_media_ffmpeg(file_path, timestamps, is_video, progress_callback)

    def _blocking_cleanup(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def cleanup(self):
        await self.loop.run_in_executor(None, self._blocking_cleanup)
