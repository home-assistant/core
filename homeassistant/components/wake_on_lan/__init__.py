"""Support for sending Wake-On-LAN magic packets."""

from functools import partial
import logging

import voluptuous as vol
import wakeonlan

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_BROADCAST_ADDRESS, CONF_BROADCAST_PORT, CONF_MAC
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SECUREON_PASSWORD, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_MAGIC_PACKET = "send_magic_packet"

WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_SECUREON_PASSWORD): cv.string,
        vol.Optional(CONF_BROADCAST_ADDRESS): cv.string,
        vol.Optional(CONF_BROADCAST_PORT): cv.port,
    }
)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the wake on LAN component."""

    async def send_magic_packet(call: ServiceCall) -> None:
        """Send magic packet to wake up a device."""
        mac_address: str = call.data[CONF_MAC]
        secureon_password = call.data.get(CONF_SECUREON_PASSWORD)
        broadcast_address = call.data.get(CONF_BROADCAST_ADDRESS)
        broadcast_port = call.data.get(CONF_BROADCAST_PORT)

        service_kwargs = {}
        if broadcast_address is not None:
            service_kwargs["ip_address"] = broadcast_address
        if broadcast_port is not None:
            service_kwargs["port"] = broadcast_port

        _LOGGER.debug(
            "Send magic packet to mac %s (secureon: %s, broadcast: %s, port: %s)",
            mac_address,
            secureon_password is not None,
            broadcast_address,
            broadcast_port,
        )

        if secureon_password:
            mac_address += f"/{secureon_password}"

        await hass.async_add_executor_job(
            partial(wakeonlan.send_magic_packet, mac_address, **service_kwargs)
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MAGIC_PACKET,
        send_magic_packet,
        schema=WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Wake on LAN component entry."""

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
