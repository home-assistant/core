"""Support for Vanderbilt (formerly Siemens) SPC alarm systems."""

from __future__ import annotations

import logging
from typing import cast

from aiohttp import ClientError
from pyspcwebgw import SpcWebGateway
from pyspcwebgw.area import Area
from pyspcwebgw.zone import Zone
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_API_URL,
    CONF_WS_URL,
    DATA_SCHEMA,
    DOMAIN,
    SIGNAL_UPDATE_ALARM,
    SIGNAL_UPDATE_SENSOR,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: DATA_SCHEMA,
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = (Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR)


class SPCConfigEntry(ConfigEntry):
    """Handle SPC config entry."""

    runtime_data: SpcWebGateway


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SPC component."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SPC from a config entry."""

    async def async_update_callback(spc_object: Area | Zone) -> None:
        """Process updates from SPC system."""
        if isinstance(spc_object, Area):
            async_dispatcher_send(hass, SIGNAL_UPDATE_ALARM.format(spc_object.id))
        elif isinstance(spc_object, Zone):
            async_dispatcher_send(hass, SIGNAL_UPDATE_SENSOR.format(spc_object.id))
        else:
            _LOGGER.warning("Received invalid update object type: %s", type(spc_object))

    session = aiohttp_client.async_get_clientsession(hass)
    entry = cast(SPCConfigEntry, entry)

    try:
        spc = SpcWebGateway(
            loop=hass.loop,
            session=session,
            api_url=entry.data[CONF_API_URL],
            ws_url=entry.data[CONF_WS_URL],
            async_callback=async_update_callback,
        )

        if not await spc.async_load_parameters():
            raise ConfigEntryNotReady("Cannot connect to SPC controller")
    except (ClientError, ConnectionError, TimeoutError) as err:
        raise ConfigEntryNotReady("Cannot connect to SPC controller") from err

    entry.runtime_data = spc

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, spc.info["sn"])},
        manufacturer="Vanderbilt",
        name=spc.info["sn"],
        model=spc.info["type"],
        sw_version=spc.info["version"],
        configuration_url=f"http://{spc.ethernet['ip_address']}/",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    spc.start()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry = cast(SPCConfigEntry, entry)
    entry.runtime_data.stop()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
