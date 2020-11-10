"""Support for System health ."""
import asyncio
import dataclasses
import logging
from typing import Callable, Dict

import async_timeout
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import integration_platform
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

DOMAIN = "system_health"

INFO_CALLBACK_TIMEOUT = 5


@bind_hass
@callback
def async_register_info(
    hass: HomeAssistant,
    domain: str,
    info_callback: Callable[[HomeAssistant], Dict],
):
    """Register an info callback.

    Deprecated.
    """
    _LOGGER.warning(
        "system_health.async_register_info is deprecated. Add a system_health platform instead."
    )
    hass.data.setdefault(DOMAIN, {}).setdefault("info", {})
    RegisterSystemHealth(hass, domain).async_register_info(info_callback)


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Set up the System Health component."""
    hass.components.websocket_api.async_register_command(handle_info)
    hass.data.setdefault(DOMAIN, {"info": {}})

    await integration_platform.async_process_integration_platforms(
        hass, DOMAIN, _register_system_health_platform
    )

    return True


async def _register_system_health_platform(hass, integration_domain, platform):
    """Register a system health platform."""
    platform.async_register(hass, RegisterSystemHealth(hass, integration_domain))


async def _info_wrapper(hass, info_callback):
    """Wrap info callback."""
    try:
        with async_timeout.timeout(INFO_CALLBACK_TIMEOUT):
            return await info_callback(hass)
    except asyncio.TimeoutError:
        return {"error": "Fetching info timed out"}
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.exception("Error fetching info")
        return {"error": str(err)}


@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "system_health/info"})
async def handle_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: Dict
):
    """Handle an info request."""
    info_callbacks = hass.data.get(DOMAIN, {}).get("info", {})
    data = {}
    data["homeassistant"] = await hass.helpers.system_info.async_get_system_info()

    if info_callbacks:
        for domain, domain_data in zip(
            info_callbacks,
            await asyncio.gather(
                *(
                    _info_wrapper(hass, info_callback)
                    for info_callback in info_callbacks.values()
                )
            ),
        ):
            data[domain] = domain_data

    connection.send_message(websocket_api.result_message(msg["id"], data))


@dataclasses.dataclass(frozen=True)
class RegisterSystemHealth:
    """Helper class to allow platforms to register."""

    hass: HomeAssistant
    domain: str

    @callback
    def async_register_info(
        self,
        info_callback: Callable[[HomeAssistant], Dict],
    ):
        """Register an info callback."""
        self.hass.data[DOMAIN]["info"][self.domain] = info_callback
