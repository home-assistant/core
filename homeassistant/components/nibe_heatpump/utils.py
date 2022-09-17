"""The Nibe Heat Pump utils."""

from __future__ import annotations

import asyncio

from . import LOGGER


class TooManyTriesException(Exception):
    """Too many retries occurred."""


def retry(retry_delays: list[float], exceptions: tuple[type[Exception]]):
    """Return a decorator to manage retries on exception."""

    def func_wrapper(func):
        async def wrapper(*args, **kwargs):
            delays = retry_delays.copy()
            while True:
                try:
                    return await func(*args, **kwargs)
                except Exception as exception:  # pylint: disable=broad-except
                    if not isinstance(exception, exceptions):
                        raise

                    LOGGER.warning(
                        "Attempt failed (%d left). Exception: %s",
                        len(delays),
                        exception,
                    )

                    if delays:
                        delay = delays.pop(0)
                        if delay > 0:
                            LOGGER.debug("Sleeping %s before retry", delay)
                            await asyncio.sleep(delay)
                    else:
                        raise TooManyTriesException() from exception

        return wrapper

    return func_wrapper
