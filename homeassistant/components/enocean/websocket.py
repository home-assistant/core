"""Web socket API for EnOcean devices."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.const import CONF_ADDRESS, CONF_TYPE
from homeassistant.core import HomeAssistant

from .const import CONF_EEP
from .helpers import get_enocean
from .types import EnOceanConfigStore


def async_get_enocean_config_store(
    func: Callable[
        [HomeAssistant, ActiveConnection, dict[str, Any], EnOceanConfigStore],
        Coroutine[Any, Any, None],
    ],
) -> Callable[
    [HomeAssistant, ActiveConnection, dict[str, Any]], Coroutine[Any, Any, None]
]:
    """Decorate function to get the EnOceanConfigStore."""

    @wraps(func)
    async def _get_enocean(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
    ) -> None:
        """Provide the EnOceanConfigStore to the function."""
        enocean = get_enocean(hass)

        await func(hass, connection, msg, enocean)

    return _get_enocean


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(CONF_TYPE): "enocean/add",
        vol.Required(CONF_ADDRESS): str,
        vol.Required(CONF_EEP): str,
    }
)
@websocket_api.async_response
@async_get_enocean_config_store
async def websocket_add(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    enocean_config_store: EnOceanConfigStore,
) -> None:
    """Add a device to config store."""
    await enocean_config_store.create_device(
        msg[CONF_ADDRESS],
        {
            CONF_ADDRESS: msg[CONF_ADDRESS],
            CONF_EEP: msg[CONF_EEP],
        },
    )
    connection.send_result(msg[CONF_ADDRESS])
