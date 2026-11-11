"""The Gree Climate integration."""

from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery_flow,
    entity_registry as er,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import CONF_IDENTIFIER, DISCOVERY_SCAN_INTERVAL, DOMAIN
from .coordinator import DeviceDataUpdateCoordinator, GreeConfigEntry
from .discovery import async_get_discovery, device_info_to_data, normalize_identifier

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SWITCH]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register domain-wide discovery shutdown."""
    discovery = async_get_discovery(hass)

    @callback
    def _async_stop(_event: Event) -> None:
        discovery.async_stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GreeConfigEntry) -> None:
    """Set up Gree Climate from a config entry."""
    if entry.unique_id == DOMAIN:
        discovery = async_get_discovery(hass)
        unloaded = False

        @callback
        def _async_mark_unloaded() -> None:
            nonlocal unloaded
            unloaded = True

        async def _async_discovery() -> None:
            try:
                devices = await discovery.async_scan()
            except OSError, TimeoutError:
                _LOGGER.warning("Unable to discover Gree devices", exc_info=True)
                return
            if unloaded or hass.is_stopping:
                return
            for info in devices.values():
                discovery_flow.async_create_flow(
                    hass,
                    DOMAIN,
                    context={"source": SOURCE_INTEGRATION_DISCOVERY},
                    data=device_info_to_data(info),
                )

        @callback
        def _async_start_discovery(_now: datetime | None = None) -> None:
            entry.async_create_background_task(
                hass, _async_discovery(), "gree discovery"
            )

        entry.async_on_unload(_async_mark_unloaded)
        entry.async_on_unload(
            async_track_time_interval(
                hass,
                _async_start_discovery,
                timedelta(seconds=DISCOVERY_SCAN_INTERVAL),
                cancel_on_shutdown=True,
            )
        )
        _async_start_discovery()
        return

    _async_transfer_legacy_records(hass, entry)
    entry.runtime_data = coordinator = DeviceDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: GreeConfigEntry) -> None:
    """Unload a config entry."""
    if entry.unique_id != DOMAIN:
        await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


@callback
def _async_transfer_legacy_records(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Transfer a confirmed device's records and inherit its legacy preferences."""
    source = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, DOMAIN)
    if source is None:
        return
    device_registry = dr.async_get(hass)
    matches = [
        (device, identifier)
        for device in dr.async_entries_for_config_entry(
            device_registry, source.entry_id
        )
        for domain, identifier in device.identifiers
        if domain == DOMAIN and normalize_identifier(identifier) == entry.unique_id
    ]
    if not matches:
        return
    if len(matches) != 1:
        raise ConfigEntryError("Multiple legacy Gree devices match this device")
    device, identifier = matches[0]
    entity_registry = er.async_get(hass)
    entities = [
        entity
        for entity in er.async_entries_for_device(
            entity_registry, device.id, include_disabled_entities=True
        )
        if entity.config_entry_id == source.entry_id
    ]
    # Keep the identifier spelling used by the existing entity unique IDs.
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_IDENTIFIER: identifier},
        pref_disable_polling=source.pref_disable_polling,
        pref_disable_new_entities=source.pref_disable_new_entities,
    )
    # Move entities first so the device update cannot remove old-owner entities.
    for entity in entities:
        entity_registry.async_update_entity(
            entity.entity_id, config_entry_id=entry.entry_id
        )
    try:
        device_registry.async_update_device(
            device.id,
            new_config_entry_id=entry.entry_id,
            disabled_by=(
                dr.DeviceEntryDisabler.USER
                if device.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
                else device.disabled_by
            ),
        )
    except HomeAssistantError:
        for entity in entities:
            entity_registry.async_update_entity(
                entity.entity_id, config_entry_id=source.entry_id
            )
        raise


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Retain legacy registry ownership while devices await confirmed enrollment."""
    if entry.version == 1:
        _LOGGER.debug("Migrating legacy Gree config entry %s", entry.entry_id)
        hass.config_entries.async_update_entry(
            entry,
            data={},
            minor_version=1,
            unique_id=DOMAIN,
            version=2,
        )
