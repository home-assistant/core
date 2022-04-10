"""The Remote Python Debugger integration."""
from __future__ import annotations

from asyncio import Event, get_running_loop
import logging
from threading import Thread

import debugpy
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

DOMAIN = "debugpy"
CONF_START = "start"
CONF_WAIT = "wait"
SERVICE_START = "start"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_HOST, default="0.0.0.0"): cv.string,
                vol.Optional(CONF_PORT, default=5678): cv.port,
                vol.Optional(CONF_START, default=True): cv.boolean,
                vol.Optional(CONF_WAIT, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Remote Python Debugger component."""
    conf = config[DOMAIN]

    async def debug_start(
        call: ServiceCall | None = None, *, wait: bool = True
    ) -> None:
        """Enable asyncio debugging and start the debugger."""
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
                debugpy.wait_for_client()
                hass.loop.call_soon_threadsafe(ready.set)

            Thread(target=waitfor).start()

            await ready.wait()
        else:
            _LOGGER.warning(
                "Listening for remote debug connection on %s:%s",
                conf[CONF_HOST],
                conf[CONF_PORT],
            )

    async_register_admin_service(
        hass, DOMAIN, SERVICE_START, debug_start, schema=vol.Schema({})
    )

    # If set to start the debugger on startup, do so
    if conf[CONF_START]:
        await debug_start(wait=conf[CONF_WAIT])

    return True
