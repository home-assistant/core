"""Helper to import modules from asyncio."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import importlib
import logging
import sys
from types import ModuleType

from homeassistant.core import HomeAssistant
from homeassistant.util.hass_dict import HassKey

_LOGGER = logging.getLogger(__name__)

DATA_IMPORT_CACHE: HassKey[dict[str, ModuleType]] = HassKey("import_cache")
DATA_IMPORT_FUTURES: HassKey[dict[str, asyncio.Future[ModuleType]]] = HassKey(
    "import_futures"
)
DATA_IMPORT_FAILURES: HassKey[dict[str, bool]] = HassKey("import_failures")


def _get_module(cache: dict[str, ModuleType], name: str) -> ModuleType:
    """Get a module."""
    cache[name] = importlib.import_module(name)
    return cache[name]


async def async_import_module(hass: HomeAssistant, name: str) -> ModuleType:
    """Import a module or return it from the cache."""
    cache = hass.data.setdefault(DATA_IMPORT_CACHE, {})
    if module := cache.get(name):
        return module

    failure_cache = hass.data.setdefault(DATA_IMPORT_FAILURES, {})
    if name in failure_cache:
        raise ModuleNotFoundError(f"{name} not found", name=name)

    import_futures = hass.data.setdefault(DATA_IMPORT_FUTURES, {})
    if future := import_futures.get(name):
        return await future

    if name in sys.modules:
        return _get_module(cache, name)

    import_future = hass.loop.create_future()
    import_futures[name] = import_future
    try:
        module = await hass.async_add_import_executor_job(_get_module, cache, name)
        import_future.set_result(module)
    except BaseException as ex:
        if isinstance(ex, ModuleNotFoundError):
            failure_cache[name] = True
        import_future.set_exception(ex)
        with suppress(BaseException):
            # Set the exception retrieved flag on the future since
            # it will never be retrieved unless there
            # are concurrent calls
            import_future.result()
        raise
    finally:
        del import_futures[name]

    return module
