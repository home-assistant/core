"""Aiohttp helpers."""
import aiohttp
from aiohttp.web_exceptions import HTTPException  # NOQA # pylint: disable=unused-import
import asyncio
import async_timeout

SESSION = aiohttp.ClientSession()


@asyncio.coroutine
def fetch(url, json=False, timeout=10):
    """Fetch a URL coroutine."""
    with async_timeout.timeout(timeout):
        resp = yield from SESSION.get(url)
        try:
            if resp.status_code != 200:
                return (resp.status_code, None)
            if json:
                return (200, (yield from resp.json()))
            else:
                return (200, (yield from resp.text()))
        except asyncio.TimeoutError:
            return (0, None)
        except Exception as err:
            resp.close()
            raise err
        finally:
            yield from resp.release()
