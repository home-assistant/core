"""Helpers for the Remote Python Debugger integration."""

from asyncio import Event, get_running_loop
import logging
from threading import Thread

import debugpy  # noqa: T100

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import CONF_WAIT, DATA_DEBUGPY_CONFIG

_LOGGER = logging.getLogger(__name__)


async def async_start_debugger(hass: HomeAssistant) -> None:
    """Enable asyncio debugging and start the debugger."""
    conf = hass.data[DATA_DEBUGPY_CONFIG]
    get_running_loop().set_debug(True)

    await hass.async_add_executor_job(
        debugpy.listen, (conf[CONF_HOST], conf[CONF_PORT])
    )

    if conf[CONF_WAIT]:
        _LOGGER.warning(
            "Waiting for remote debug connection on %s:%s",
            conf[CONF_HOST],
            conf[CONF_PORT],
        )
        ready = Event()

        def waitfor():
            debugpy.wait_for_client()  # noqa: T100
            hass.loop.call_soon_threadsafe(ready.set)

        Thread(target=waitfor).start()

        await ready.wait()
    else:
        _LOGGER.warning(
            "Listening for remote debug connection on %s:%s",
            conf[CONF_HOST],
            conf[CONF_PORT],
        )
