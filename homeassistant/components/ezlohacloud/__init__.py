"""The Ezlo HA Cloud integration."""

# from __future__ import annotations

# from homeassistant.config_entries import ConfigEntry
# from homeassistant.const import Platform
# from homeassistant.core import HomeAssistant

# PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]

# # Alias name should be prefixed by integration name
# type New_NameConfigEntry = ConfigEntry[MyApi]  # noqa: F821


# async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
#     """Set up Ezlo HA Cloud from a config entry."""

#     # entry.runtime_data = MyAPI(...)

#     await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

#     return True

# async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
#     """Unload a config entry."""
#     return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

import asyncio
import logging
import socket

from snitun.client.client_peer import ClientPeer
from snitun.client.connector import Connector
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

CONF_USERNAME = "username"
CONF_PASSWORD = "password"

AES_KEY = bytes.fromhex("b65d3f7abe71344a5abc2471dad1e42a")
AES_IV = bytes.fromhex("596c63ed250ffb99f37e2f2cf8ca01eb")

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Init ezlo ha cloud."""

    _LOGGER.info("Ezlo ha cloud setup finished")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # noqa: D103
    _LOGGER.info("####################")

    _LOGGER.info(entry.data.get("sni_host"))

    ha_ip = get_local_ip()
    ha_port = 8123

    client = ClientPeer(
        snitun_host=entry.data.get("sni_host"), snitun_port=entry.data.get("sni_port")
    )
    connector = Connector(end_host=ha_ip, end_port=ha_port)

    fernet_token = entry.data.get("fernet_token")
    if not fernet_token:
        _LOGGER.error("Fernet token is missing from configuration")
        return False

    await client.start(
        connector,
        fernet_token=fernet_token.encode("utf-8"),
        aes_key=AES_KEY,
        aes_iv=AES_IV,
    )

    stop_event = asyncio.Event()
    await stop_event.wait()

    return True


def get_local_ip():
    """Get the IP address of the local machine (Home Assistant instance)."""
    try:
        # Connect to a public DNS server (like Google DNS) and get the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(("8.8.8.8", 1))  # You don't need to send data; just connecting works
        local_ip = s.getsockname()[0]
    except Exception:  # noqa: BLE001
        local_ip = "127.0.0.1"  # Fallback to localhost if there's an issue
    finally:
        s.close()

    return local_ip


# async def get_local_ip(hass):
#     """Get the local IP address using Home Assistant's network component."""

#     # Get the instance of the network helper
#     network_obj = await network.async_get_network(hass)

#     # Check if there are configured adapters with IPv4 addresses
#     if network_obj.configured_adapters:
#         for adapter in network_obj.configured_adapters:
#             if adapter.ipv4:
#                 return adapter.ipv4[
#                     0
#                 ].address  # Return the first available IPv4 address

#     # Fallback in case no IP address is found
#     _LOGGER.error("No configured adapters or IPv4 address found.")

#     return None
