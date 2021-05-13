"""Support for AVM Fritz!Box functions."""
from __future__ import annotations

import logging

from fritzconnection.core.exceptions import FritzConnectionException, FritzSecurityError

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import (
    async_get_registry as async_get_dev_registry,
)
from homeassistant.helpers.entity_registry import (
    async_get_registry as async_get_ent_registry,
)

from .common import FritzBoxTools
from .const import (
    CONF_SELECTED_DEVICES,
    DATA_ACTIVE_TRACKER,
    DATA_KNOWN_DEVICES,
    DOMAIN,
    FRITZ_TOOLS,
    PLATFORMS,
    UNDO_UPDATE_LISTENER_OPTIONS,
    UNDO_UPDATE_LISTENER_TRACKER,
)
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up fritzboxtools from config entry."""
    _LOGGER.debug("Setting up FRITZ!Box Tools component")
    fritz_tools = FritzBoxTools(
        hass=hass,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    try:
        await fritz_tools.async_setup()
        await fritz_tools.async_start()
    except FritzSecurityError as ex:
        raise ConfigEntryAuthFailed from ex
    except FritzConnectionException as ex:
        raise ConfigEntryNotReady from ex

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        FRITZ_TOOLS: fritz_tools,
        DATA_ACTIVE_TRACKER: {},
        DATA_KNOWN_DEVICES: [],
        UNDO_UPDATE_LISTENER_OPTIONS: entry.add_update_listener(_async_update_listener),
        UNDO_UPDATE_LISTENER_TRACKER: None,
    }

    @callback
    def _async_unload(event):
        fritz_tools.async_unload()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_unload)
    )
    # Load the other platforms like switch
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload FRITZ!Box Tools config entry."""
    _LOGGER.debug("async_unload_entry()")

    entry_data = hass.data[DOMAIN][entry.entry_id]

    fritzbox: FritzBoxTools = entry_data[FRITZ_TOOLS]
    fritzbox.async_unload()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        if callable(entry_data[UNDO_UPDATE_LISTENER_TRACKER]):
            entry_data[UNDO_UPDATE_LISTENER_TRACKER]()
        entry_data[UNDO_UPDATE_LISTENER_OPTIONS]()
        hass.data[DOMAIN].pop(entry.entry_id)

    await async_unload_services(hass)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    active_tracker: dict[str, bool] = hass.data[DOMAIN][entry.entry_id][
        DATA_ACTIVE_TRACKER
    ]
    selected_devices: list[str] = entry.options[CONF_SELECTED_DEVICES]

    ent_reg = await async_get_ent_registry(hass)
    dev_reg = await async_get_dev_registry(hass)

    for tracker in active_tracker:
        if tracker not in selected_devices:
            entity_id = ent_reg.async_get_entity_id(
                DEVICE_TRACKER_DOMAIN, DOMAIN, tracker
            )
            if entity_id:
                entity = ent_reg.async_get(entity_id)
                if entity and entity.device_id is not None:
                    await hass.async_add_executor_job(
                        dev_reg.async_remove_device, entity.device_id
                    )

    await hass.config_entries.async_reload(entry.entry_id)
