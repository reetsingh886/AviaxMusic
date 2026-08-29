# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import os
import re
import random
import asyncio
from pathlib import Path

import aiohttp
import yt_dlp

from py_yt import Playlist, VideosSearch

from anony import config, logger
from anony.helpers import NexGenApi, Track, utils


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="

        self.cookies = []
        self.checked = False
        self.warned = False

        self.cookie_dir = "anony/cookies"

        # Make sure required directories exist.
        Path(self.cookie_dir).mkdir(parents=True, exist_ok=True)
        Path("downloads").mkdir(parents=True, exist_ok=True)

        # ─────────────────────────────────────────────
        # NexGen API
        # Single API URL for BOTH audio and video
        # ─────────────────────────────────────────────
        self.api = None

        api_url = getattr(config, "API_URL", None)
        api_key = getattr(config, "API_KEY", None)

        if api_url and api_key:
            try:
                self.api = NexGenApi(
                    api_url,
                    api_key,
                )
                logger.info("NexGen API initialized successfully.")
            except Exception as ex:
                self.api = None
                logger.warning(
                    "NexGen API initialization failed: %s",
                    ex,
                )
        else:
            logger.warning(
                "API_URL/API_KEY missing. "
                "Using yt-dlp fallback."
            )

        # ─────────────────────────────────────────────
        # YouTube URL validation
        # ─────────────────────────────────────────────

        self.regex = re.compile(
            r"(https?://)?"
            r"(www\.|m\.|music\.)?"
            r"(youtube\.com/"
            r"(watch\?v=|shorts/|playlist\?list=)|"
            r"youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)"
            r"([&?][^\s]*)?"
        )

        self.iregex = re.compile(
            r"https?://"
            r"(?:www\.|m\.|music\.)?"
            r"(?:youtube\.com|youtu\.be)"
            r"(?!/"
            r"(watch\?v=[A-Za-z0-9_-]{11}|"
            r"shorts/[A-Za-z0-9_-]{11}|"
            r"playlist\?list=PL[A-Za-z0-9_-]+|"
            r"[A-Za-z0-9_-]{11})"
            r")\S*"
        )

    # ─────────────────────────────────────────────
    # Cookies
    # ─────────────────────────────────────────────

    def get_cookies(self):
        if not self.checked:
            self.cookies.clear()

            try:
                for file in os.listdir(self.cookie_dir):
                    if file.endswith(".txt"):
                        self.cookies.append(
                            os.path.join(
                                self.cookie_dir,
                                file,
                            )
                        )
            except Exception as ex:
                logger.warning(
                    "Unable to read cookie directory: %s",
                    ex,
                )

            self.checked = True

        if not self.cookies:
            if not self.warned:
                self.warned = True
                logger.warning(
                    "YouTube cookies are missing. "
                    "yt-dlp fallback may fail."
                )

            return None

        return random.choice(self.cookies)

    async def save_cookies(self, urls: list[str]) -> None:
        logger.info("Saving YouTube cookies...")

        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    name = url.rstrip("/").split("/")[-1]

                    if not name:
                        continue

                    raw_url = (
                        f"https://batbin.me/raw/{name}"
                    )

                    cookie_path = os.path.join(
                        self.cookie_dir,
                        f"{name}.txt",
                    )

                    async with session.get(
                        raw_url,
                        timeout=aiohttp.ClientTimeout(
                            total=30
                        ),
                    ) as resp:
                        resp.raise_for_status()

                        data = await resp.read()

                    with open(
                        cookie_path,
                        "wb",
                    ) as fw:
                        fw.write(data)

                    if cookie_path not in self.cookies:
                        self.cookies.append(cookie_path)

                    logger.info(
                        "Cookie saved: %s",
                        cookie_path,
                    )

                except Exception as ex:
                    logger.warning(
                        "Failed to save cookie: %s",
                        ex,
                    )

        logger.info(
            "Cookie saving process completed."
        )

    # ─────────────────────────────────────────────
    # URL validation
    # ─────────────────────────────────────────────

    def valid(self, url: str) -> bool:
        return bool(self.regex.match(url))

    def invalid(self, url: str) -> bool:
        return bool(self.iregex.match(url))

    # ─────────────────────────────────────────────
    # YouTube search
    # ─────────────────────────────────────────────

    async def search(
        self,
        query: str,
        m_id: int,
        video: bool = False,
    ) -> Track | None:

        try:
            search = VideosSearch(
                query,
                limit=1,
                with_live=False,
            )

            results = await search.next()

        except Exception as ex:
            logger.warning(
                "YouTube search failed: %s",
                ex,
            )
            return None

        if not results:
            return None

        result_list = results.get("result")

        if not result_list:
            return None

        data = result_list[0]

        thumbnails = data.get("thumbnails") or []

        thumbnail = ""

        if thumbnails:
            thumbnail = (
                thumbnails[-1].get("url") or ""
            ).split("?")[0]

        title = data.get("title") or ""

        duration = data.get("duration")

        channel = data.get("channel") or {}

        view_count = data.get("viewCount") or {}

        return Track(
            id=data.get("id"),
            channel_name=channel.get(
                "name",
                "",
            ),
            duration=duration,
            duration_sec=utils.to_seconds(
                duration
            ),
            message_id=m_id,
            title=title[:25],
            thumbnail=thumbnail,
            url=data.get("link"),
            view_count=view_count.get(
                "short",
                "",
            ),
            video=video,
        )

    # ─────────────────────────────────────────────
    # Playlist
    # ─────────────────────────────────────────────

    async def playlist(
        self,
        limit: int,
        user: str,
        url: str,
        video: bool,
    ) -> list[Track]:

        tracks = []

        try:
            playlist = await Playlist.get(url)

            videos = playlist.get(
                "videos",
                [],
            )

            for data in videos[:limit]:

                thumbnails = (
                    data.get("thumbnails") or []
                )

                thumbnail = ""

                if thumbnails:
                    thumbnail = (
                        thumbnails[-1].get(
                            "url"
                        ) or ""
                    ).split("?")[0]

                duration = data.get(
                    "duration"
                )

                link = data.get(
                    "link",
                    "",
                )

                if "&list=" in link:
                    link = link.split(
                        "&list="
                    )[0]

                channel = (
                    data.get("channel") or {}
                )

                tracks.append(
                    Track(
                        id=data.get("id"),
                        channel_name=channel.get(
                            "name",
                            "",
                        ),
                        duration=duration,
                        duration_sec=utils.to_seconds(
                            duration
                        ),
                        title=(
                            data.get("title")
                            or ""
                        )[:25],
                        thumbnail=thumbnail,
                        url=link,
                        user=user,
                        view_count="",
                        video=video,
                    )
                )

        except Exception as ex:
            logger.warning(
                "YouTube playlist failed: %s",
                ex,
            )

        return tracks

    # ─────────────────────────────────────────────
    # Download
    # ─────────────────────────────────────────────

    async def download(
        self,
        video_id: str,
        video: bool = False,
    ) -> str | None:

        # ─────────────────────────────────────────
        # 1. NexGen API
        # One API for audio + video
        # ─────────────────────────────────────────

        if self.api:
            try:
                logger.info(
                    "Trying NexGen API for %s | video=%s",
                    video_id,
                    video,
                )

                file_path = await self.api.download(
                    video_id,
                    video,
                )

                if file_path:
                    path = Path(str(file_path))

                    if path.exists():
                        logger.info(
                            "NexGen API download successful: %s",
                            path,
                        )
                        return str(path)

                    logger.warning(
                        "NexGen API returned a path "
                        "that does not exist: %s",
                        file_path,
                    )

            except Exception as ex:
                logger.warning(
                    "NexGen API download failed: %s",
                    ex,
                )

        # ─────────────────────────────────────────
        # 2. Local cache
        # ─────────────────────────────────────────

        url = self.base + video_id

        expected_extension = (
            "mp4" if video else "webm"
        )

        expected_file = Path(
            f"downloads/{video_id}."
            f"{expected_extension}"
        )

        if expected_file.exists():
            return str(expected_file)

        # ─────────────────────────────────────────
        # 3. yt-dlp fallback
        # ─────────────────────────────────────────

        cookie = self.get_cookies()

        base_opts = {
            "outtmpl": (
                "downloads/%(id)s.%(ext)s"
            ),
            "quiet": True,
            "noplaylist": True,
            "geo_bypass": True,
            "no_warnings": True,
            "overwrites": False,
            "nocheckcertificate": True,
            "retries": 3,
            "fragment_retries": 3,
        }

        if cookie:
            base_opts["cookiefile"] = cookie

        if video:
            ydl_opts = {
                **base_opts,
                "format": (
                    "(bestvideo[height<=720]"
                    "[width<=1280][ext=mp4]"
                    "+bestaudio)/best"
                ),
                "merge_output_format": "mp4",
            }

        else:
            ydl_opts = {
                **base_opts,
                "format": (
                    "bestaudio[ext=webm]"
                    "[acodec=opus]/"
                    "bestaudio/best"
                ),
            }

        def _download():

            try:
                with yt_dlp.YoutubeDL(
                    ydl_opts
                ) as ydl:

                    result = ydl.download(
                        [url]
                    )

                    if result != 0:
                        return None

                # Exact expected file
                if expected_file.exists():
                    return str(
                        expected_file
                    )

                # yt-dlp can sometimes produce
                # a different extension.
                matches = list(
                    Path("downloads").glob(
                        f"{video_id}.*"
                    )
                )

                if matches:
                    return str(
                        matches[0]
                    )

            except (
                yt_dlp.utils.DownloadError,
                yt_dlp.utils.ExtractorError,
            ) as ex:

                logger.warning(
                    "yt-dlp download failed: %s",
                    ex,
                )

            except Exception as ex:

                logger.warning(
                    "Unexpected yt-dlp error: %s",
                    ex,
                )

            return None

        return await asyncio.to_thread(
            _download
        )
