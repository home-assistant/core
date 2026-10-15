"""Support for Xiaomi Gateways."""

import asyncio
from dataclasses import dataclass, field
import logging

from xiaomi_gateway import AsyncXiaomiGatewayMulticast, XiaomiGateway

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PROTOCOL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import CONF_INTERFACE, CONF_KEY, CONF_SID, DEFAULT_DISCOVERY_RETRY, DOMAIN
from .services import setup_services

type XiaomiAqaraConfigEntry = ConfigEntry[XiaomiGateway]

_LOGGER = logging.getLogger(__name__)

GATEWAY_PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
]
GATEWAY_PLATFORMS_NO_KEY = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Xiaomi component."""
    setup_services(hass)
    return True


@dataclass
class XiaomiAqaraData:
    """Multicast listener shared by every gateway."""

    setup_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    multicast: AsyncXiaomiGatewayMulticast | None = None
    unsub_stop: CALLBACK_TYPE | None = None


# One multicast listener serves every gateway, so it is shared between config
# entries rather than owned by any one of them.
XIAOMI_AQARA_DATA: HassKey[XiaomiAqaraData] = HassKey(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: XiaomiAqaraConfigEntry) -> None:
    """Set up the xiaomi aqara components from a config entry."""
    if (data := hass.data.get(XIAOMI_AQARA_DATA)) is None:
        data = hass.data[XIAOMI_AQARA_DATA] = XiaomiAqaraData()

    # Connect to Xiaomi Aqara Gateway
    xiaomi_gateway = await hass.async_add_executor_job(
        XiaomiGateway,
        entry.data[CONF_HOST],
        entry.data[CONF_SID],
        entry.data[CONF_KEY],
        DEFAULT_DISCOVERY_RETRY,
        entry.data[CONF_INTERFACE],
        entry.data[CONF_PORT],
        entry.data[CONF_PROTOCOL],
    )
    entry.runtime_data = xiaomi_gateway

    async with data.setup_lock:
        if (multicast := data.multicast) is None:
            multicast = AsyncXiaomiGatewayMulticast(
                interface=entry.data[CONF_INTERFACE]
            )
            data.multicast = multicast

            # start listining for local pushes (only once)
            await multicast.start_listen()

            # register stop callback to shutdown listining for local pushes
            @callback
            def stop_xiaomi(event):
                """Stop Xiaomi Socket."""
                _LOGGER.debug("Shutting down Xiaomi Gateway Listener")
                multicast.stop_listen()

            data.unsub_stop = hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, stop_xiaomi
            )

    multicast.register_gateway(entry.data[CONF_HOST], xiaomi_gateway.multicast_callback)
    _LOGGER.debug(
        "Gateway with host '%s' connected, listening for broadcasts",
        entry.data[CONF_HOST],
    )

    assert entry.unique_id
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer="Xiaomi Aqara",
        name=entry.title,
        sw_version=entry.data[CONF_PROTOCOL],
    )

    if entry.data[CONF_KEY] is not None:
        platforms = GATEWAY_PLATFORMS
    else:
        platforms = GATEWAY_PLATFORMS_NO_KEY

    await hass.config_entries.async_forward_entry_setups(entry, platforms)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: XiaomiAqaraConfigEntry
) -> None:
    """Unload a config entry."""
    if config_entry.data[CONF_KEY] is not None:
        platforms = GATEWAY_PLATFORMS
    else:
        platforms = GATEWAY_PLATFORMS_NO_KEY

    try:
        await hass.config_entries.async_unload_platforms_or_raise(
            config_entry, platforms
        )
    finally:
        if not hass.config_entries.async_loaded_entries(DOMAIN):
            # No gateways left, stop Xiaomi socket
            data = hass.data[XIAOMI_AQARA_DATA]
            if data.unsub_stop is not None:
                data.unsub_stop()
                data.unsub_stop = None
            _LOGGER.debug("Shutting down Xiaomi Gateway Listener")
            if data.multicast is not None:
                data.multicast.stop_listen()
                data.multicast = None
