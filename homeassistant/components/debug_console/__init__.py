"""The Debug console integration, running Python inside Home Assistant."""

import probatio

from homeassistant.const import CONF_ENABLED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, IS_DEVELOPMENT_VERSION
from .safeguards import async_setup_safeguards
from .session import DATA_SESSIONS, async_close_sessions
from .websocket_api import async_register_websocket_commands

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {probatio.Optional(CONF_ENABLED, default=True): cv.boolean}
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Debug console.

    Development and nightly versions load it without configuration, so it is
    on there, unless disabled. Other versions need it in YAML, which a browser
    cannot add: code in the browser of an administrator, like a custom card,
    could otherwise enable the console and run code unnoticed.
    """
    turned_on = config.get(DOMAIN, {}).get(CONF_ENABLED, True)
    enabled = (IS_DEVELOPMENT_VERSION or DOMAIN in config) and turned_on

    if enabled:
        sessions = hass.data[DATA_SESSIONS] = {}
        await async_setup_safeguards(hass)

        # Integrations are not unloaded on shutdown, but code still running in
        # the console should stop then too.
        async def _async_close_sessions(_event: Event) -> None:
            await async_close_sessions(sessions)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close_sessions)

    async_register_websocket_commands(hass, enabled=enabled)
    return True
