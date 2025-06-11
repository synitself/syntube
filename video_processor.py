# (Код video_processor.py из предыдущего ответа остается актуальным,
# но с одним дополнением для создания прогресс-бара)
import os
import re
import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

import yt_dlp
from pydub import AudioSegment
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
import logging

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
        """Создает текстовый прогресс-бар."""
        percentage = max(0, min(100, percentage))
        filled_length = int(length * percentage // 100)
        bar = '█' * filled_length + '░' * (length - filled_length)
        return f"[{bar}] {percentage}%"

    # ... (остальной код video_processor.py из предыдущего ответа остается здесь) ...
    # (get_video_info, parse_timestamps, get_chapters_from_video_info, download_media, etc.)

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
        cleaned = re.sub(r'[<>:"/\\|?*]', '', name)
        cleaned = re.sub(r'^\d+[.\s]*', '', cleaned)
        cleaned = cleaned.strip()
        return cleaned if cleaned else 'Unnamed Track'

    def sanitize_filename(self, filename: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', '', filename).strip()

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
        self.thumbnail_path = self.temp_dir / f"thumbnail_{video_id}{file_ext}"
        with open(self.thumbnail_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
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

    async def download_media(self, video_url: str, is_video: bool = True, progress_callback=None) -> Path:
        format_selector = 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' if is_video else 'bestaudio[ext=m4a]/bestaudio/best'
        safe_title = self.sanitize_filename(self.video_info['title'])
        output_template = self.temp_dir / f'{safe_title}.%(ext)s'
        ydl_opts = {'format': format_selector, 'outtmpl': str(output_template), 'quiet': True, 'no_warnings': True}
        if not is_video:
            ydl_opts['postprocessors'] = [
                {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await self.loop.run_in_executor(None, lambda: ydl.download([video_url]))

        ext = 'mp4' if is_video else 'mp3'
        expected_file = self.temp_dir / f"{safe_title}.{ext}"
        if expected_file.exists(): return expected_file

        search_ext = ['.mp4', '.mkv', '.webm'] if is_video else ['.mp3', '.m4a', '.opus']
        for file_path in self.temp_dir.glob(f"{safe_title}.*"):
            if file_path.suffix.lower() in search_ext: return file_path

        raise FileNotFoundError(f"Загруженный файл не найден: {expected_file}")

    def _blocking_add_metadata(self, file_path: Path, title: str, artist: str, album: str):
        try:
            audio = MP3(str(file_path), ID3=ID3)
            if audio.tags is None: audio.add_tags()

            audio.tags.delall('TIT2')
            audio.tags.add(TIT2(encoding=3, text=title))

            audio.tags.delall('TPE1')
            audio.tags.add(TPE1(encoding=3, text=artist))

            audio.tags.delall('TALB')
            audio.tags.add(TALB(encoding=3, text=album))

            audio.tags.delall('APIC')
            if self.thumbnail_path and self.thumbnail_path.exists():
                with open(self.thumbnail_path, 'rb') as art:
                    mime = 'image/jpeg'
                    if self.thumbnail_path.suffix.lower() == '.png':
                        mime = 'image/png'
                    elif self.thumbnail_path.suffix.lower() == '.webp':
                        mime = 'image/webp'
                    audio.tags.add(APIC(encoding=3, mime=mime, type=3, desc='Cover', data=art.read()))
            audio.save()
        except Exception as e:
            logger.warning(f"Ошибка добавления метаданных в {file_path.name}: {e}")

    async def add_metadata_to_audio(self, file_path: Path, title: str, artist: str, album: str):
        await self.loop.run_in_executor(None, self._blocking_add_metadata, file_path, title, artist, album)

    def _blocking_split_audio(self, file_path, timestamps):
        audio = AudioSegment.from_file(str(file_path))
        segments_data = []
        total_duration_ms = len(audio)
        for i, (start_time, title) in enumerate(timestamps):
            start_ms = start_time * 1000
            end_ms = timestamps[i + 1][0] * 1000 if i + 1 < len(timestamps) else total_duration_ms
            segment = audio[start_ms:end_ms]
            clean_title = self.sanitize_filename(title)
            segment_path = self.temp_dir / f"{i + 1:02d}. {clean_title}.mp3"
            segment.export(str(segment_path), format="mp3", bitrate="192k")
            segments_data.append((segment_path, clean_title))
        return segments_data

    async def split_audio_pydub(self, file_path: Path, timestamps: List[Tuple[int, str]], progress_callback=None) -> \
    List[Path]:
        segments_data = await self.loop.run_in_executor(None, self._blocking_split_audio, file_path, timestamps)

        segments = []
        video_title_as_artist_and_album = self.video_info.get('title', 'Unknown Album')

        for i, (segment_path, clean_title) in enumerate(segments_data):
            await self.add_metadata_to_audio(
                file_path=segment_path,
                title=clean_title,
                artist=video_title_as_artist_and_album,
                album=video_title_as_artist_and_album
            )
            segments.append(segment_path)
            if progress_callback:
                await progress_callback(int((i + 1) / len(segments_data) * 100))
        return segments

    async def split_media(self, file_path: Path, timestamps: List[Tuple[int, str]], is_video: bool = True,
                          progress_callback=None) -> List[Path]:
        if is_video:
            # Логика для видео здесь не реализована полностью, так как фокус на аудио
            raise NotImplementedError("Video splitting is not supported in this version.")
        else:
            return await self.split_audio_pydub(file_path, timestamps, progress_callback)

    def _blocking_cleanup(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def cleanup(self):
        await self.loop.run_in_executor(None, self._blocking_cleanup)