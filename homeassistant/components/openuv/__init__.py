"""Support for UV data from openuv.io."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

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
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_FROM_WINDOW,
    CONF_TO_WINDOW,
    DATA_PROTECTION_WINDOW,
    DATA_UV,
    DEFAULT_FROM_WINDOW,
    DEFAULT_TO_WINDOW,
    DOMAIN,
    LOGGER,
    TYPE_PROTECTION_WINDOW,
)
from .coordinator import OpenUvCoordinator

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

    async def async_update_protection_data() -> dict[str, Any]:
        """Update binary sensor (protection window) data."""
        low = entry.options.get(CONF_FROM_WINDOW, DEFAULT_FROM_WINDOW)
        high = entry.options.get(CONF_TO_WINDOW, DEFAULT_TO_WINDOW)
        return await client.uv_protection_window(low=low, high=high)

    coordinators: dict[str, OpenUvCoordinator] = {
        coordinator_name: OpenUvCoordinator(
            hass,
            entry=entry,
            name=coordinator_name,
            latitude=client.latitude,
            longitude=client.longitude,
            update_method=update_method,
        )
        for coordinator_name, update_method in (
            (DATA_UV, client.uv_index),
            (DATA_PROTECTION_WINDOW, async_update_protection_data),
        )
    }

    init_tasks = [
        coordinator.async_config_entry_first_refresh()
        for coordinator in coordinators.values()
    ]
    await asyncio.gather(*init_tasks)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Schedule a once-per-morning update for the protection window coordinator (always
    # at the same local time every morning):
    async def async_refresh_protection_window_coordinator(_: datetime) -> None:
        """Schedule a manual refresh of the protection window coordinator."""
        await coordinators[DATA_PROTECTION_WINDOW].async_refresh()

    entry.async_on_unload(
        async_track_utc_time_change(
            hass,
            async_refresh_protection_window_coordinator,
            hour=1,
            minute=0,
            second=0,
            local=True,
        )
    )

    # Automations to update the protection window binary sensor are deprecated (in favor
    # of an automatic update); create issue registry entries for every such automation
    # we find:
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

    return True


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
