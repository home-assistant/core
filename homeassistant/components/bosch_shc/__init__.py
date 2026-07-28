"""The Bosch Smart Home Controller integration."""

import logging
from typing import TYPE_CHECKING

from boschshcpy import SHCSessionAsync
from boschshcpy.api import JSONRPCError
from boschshcpy.api_async import build_ssl_context
from boschshcpy.exceptions import (
    SHCAuthenticationError,
    SHCConnectionError,
    SHCSessionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CONF_SSL_CERTIFICATE, CONF_SSL_KEY, DOMAIN

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


type BoschConfigEntry = ConfigEntry[SHCSessionAsync]


async def async_setup_entry(hass: HomeAssistant, entry: BoschConfigEntry) -> bool:
    """Set up Bosch SHC from a config entry."""
    data = entry.data

    # build_ssl_context() reads the cert/key files (blocking I/O), so it must
    # not run directly on the event loop.
    try:
        ssl_context = await hass.async_add_executor_job(
            build_ssl_context, data[CONF_SSL_CERTIFICATE], data[CONF_SSL_KEY]
        )
    except (OSError, ValueError) as err:
        raise ConfigEntryAuthFailed from err
    session = SHCSessionAsync(
        data[CONF_HOST],
        data[CONF_SSL_CERTIFICATE],
        data[CONF_SSL_KEY],
        ssl_context=ssl_context,
    )
    try:
        await session.async_init()
    except SHCAuthenticationError as err:
        await session.api.close()
        raise ConfigEntryAuthFailed from err
    except (SHCConnectionError, SHCSessionError) as err:
        await session.api.close()
        raise ConfigEntryNotReady from err
    except BaseException:
        await session.api.close()
        raise

    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None
    if shc_info.update_state == "UPDATE_AVAILABLE":
        _LOGGER.warning("Please check for software updates in the Bosch Smart Home App")

    entry.runtime_data = session

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, shc_info.unique_id)},
        identifiers={(DOMAIN, shc_info.unique_id)},
        manufacturer="Bosch",
        name=entry.title,
        model="SmartHomeController",
        sw_version=shc_info.version,
    )

    try:
        await session.start_polling()
    except (SHCConnectionError, SHCSessionError, JSONRPCError) as err:
        # subscribe (RE/subscribe) is a real network call.
        await session.api.close()
        raise ConfigEntryNotReady from err
    except BaseException:
        await session.api.close()
        raise

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def stop_polling(event):
        """Stop polling service."""
        await session.stop_polling()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_polling)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BoschConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.stop_polling()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
