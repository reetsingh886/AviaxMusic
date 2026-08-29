# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import asyncio
import signal
import importlib
from contextlib import suppress

from anony import (
    anon,
    app,
    config,
    db,
    logger,
    stop,
    thumb,
    userbot,
    yt,
)
from anony.plugins import all_modules


async def idle():
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGABRT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()


async def main():
    # Database
    await db.connect()

    # Main bot
    await app.boot()

    # Userbot
    await userbot.boot()

    # Anonymous client
    await anon.boot()

    # Thumbnail service
    await thumb.start()

    # Load plugins
    for module in all_modules:
        importlib.import_module(f"anony.plugins.{module}")

    logger.info(f"Loaded {len(all_modules)} modules.")

    # Save YouTube cookies if configured
    if config.COOKIES_URL:
        await yt.save_cookies(config.COOKIES_URL)

    # YouTube API session initialization is NOT required.
    # The current YouTube class directly uses SHRUTI_API_URL
    # for both audio and video downloads.

    # Load sudo users
    sudoers = await db.get_sudoers()
    app.sudoers.update(sudoers)

    # Load blacklisted users
    app.bl_users.update(await db.get_blacklisted())

    logger.info(f"Loaded {len(app.sudoers)} sudo users.")

    # Keep bot running
    await idle()

    # Shutdown
    await stop()


if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        pass
