"""Support for UV data from openuv.io."""
from __future__ import annotations

import asyncio

from pyopenuv import Client

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_BINARY_SENSORS,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SENSORS,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATA_PROTECTION_WINDOW,
    DATA_UV,
    DOMAIN,
    LOGGER,
    TYPE_PROTECTION_WINDOW,
)
from .coordinator import (
    OpenUvCoordinator,
    ProtectionWindowCoordinator,
    UvIndexCoordinator,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenUV as config entry."""
    latitude = entry.data.get(CONF_LATITUDE, hass.config.latitude)
    longitude = entry.data.get(CONF_LONGITUDE, hass.config.longitude)

    websession = aiohttp_client.async_get_clientsession(hass)
    client = Client(
        entry.data[CONF_API_KEY],
        latitude,
        longitude,
        altitude=entry.data.get(CONF_ELEVATION, hass.config.elevation),
        session=websession,
        check_status_before_request=True,
    )

    coordinators = {
        DATA_PROTECTION_WINDOW: ProtectionWindowCoordinator(hass, entry, client),
        DATA_UV: UvIndexCoordinator(hass, entry, client),
    }

    init_tasks = [
        coordinator.async_config_entry_first_refresh()
        for coordinator in coordinators.values()
    ]
    await asyncio.gather(*init_tasks)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Automations to update the protection window binary sensor are deprecated (in favor
    # of automatic updates); create issue registry entries for every such automation we
    # find:
    ent_reg = er.async_get(hass)
    protection_window_registry_entry = ent_reg.async_get_or_create(
        BINARY_SENSOR_DOMAIN, DOMAIN, f"{latitude}_{longitude}_{TYPE_PROTECTION_WINDOW}"
    )
    for automation_entity_id in automations_with_entity(
        hass, protection_window_registry_entry.entity_id
    ):
        async_create_issue(
            hass,
            DOMAIN,
            f"protection_window_automation_{automation_entity_id}",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="protection_window_automation",
            translation_placeholders={
                "automation_entity_id": automation_entity_id,
                "protection_window_entity_id": protection_window_registry_entry.entity_id,
            },
        )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an OpenUV config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate the config entry upon new versions."""
    version = entry.version
    data = {**entry.data}

    LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Remove unused condition data:
    if version == 1:
        data.pop(CONF_BINARY_SENSORS, None)
        data.pop(CONF_SENSORS, None)
        version = entry.version = 2
        hass.config_entries.async_update_entry(entry, data=data)
        LOGGER.debug("Migration to version %s successful", version)

    return True


class OpenUvEntity(CoordinatorEntity):
    """Define a generic OpenUV entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: OpenUvCoordinator, description: EntityDescription
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_extra_state_attributes = {}
        self._attr_unique_id = (
            f"{coordinator.latitude}_{coordinator.longitude}_{description.key}"
        )
        self.entity_description = description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.latitude}_{coordinator.longitude}")},
            name="OpenUV",
            entry_type=DeviceEntryType.SERVICE,
        )
