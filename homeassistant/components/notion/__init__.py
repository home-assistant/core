"""Support for Notion."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from aionotion import async_get_client
from aionotion.errors import InvalidCredentialsError, NotionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, LOGGER

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

ATTR_SYSTEM_MODE = "system_mode"
ATTR_SYSTEM_NAME = "system_name"

DEFAULT_ATTRIBUTION = "Data provided by Notion"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Notion as a config entry."""
    if not entry.unique_id:
        hass.config_entries.async_update_entry(
            entry, unique_id=entry.data[CONF_USERNAME]
        )

    session = aiohttp_client.async_get_clientsession(hass)

    try:
        client = await async_get_client(
            entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session=session
        )
    except InvalidCredentialsError as err:
        raise ConfigEntryAuthFailed("Invalid username and/or password") from err
    except NotionError as err:
        raise ConfigEntryNotReady("Config entry failed to load") from err

    async def async_update() -> dict[str, dict[str, Any]]:
        """Get the latest data from the Notion API."""
        data: dict[str, dict[str, Any]] = {"bridges": {}, "sensors": {}, "tasks": {}}
        tasks = {
            "bridges": client.bridge.async_all(),
            "sensors": client.sensor.async_all(),
            "tasks": client.task.async_all(),
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for attr, result in zip(tasks, results):
            if isinstance(result, InvalidCredentialsError):
                raise ConfigEntryAuthFailed(
                    "Invalid username and/or password"
                ) from result
            if isinstance(result, NotionError):
                raise UpdateFailed(
                    f"There was a Notion error while updating {attr}: {result}"
                ) from result
            if isinstance(result, Exception):
                raise UpdateFailed(
                    f"There was an unknown error while updating {attr}: {result}"
                ) from result

            for item in result:
                if attr == "bridges" and item["id"] not in data["bridges"]:
                    # If a new bridge is discovered, register it:
                    _async_register_new_bridge(hass, item, entry)
                data[attr][item["id"]] = item

        return data

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=entry.data[CONF_USERNAME],
        update_interval=DEFAULT_SCAN_INTERVAL,
        update_method=async_update,
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Notion config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


@callback
def _async_register_new_bridge(
    hass: HomeAssistant, bridge: dict, entry: ConfigEntry
) -> None:
    """Register a new bridge."""
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, bridge["hardware_id"])},
        manufacturer="Silicon Labs",
        model=bridge["hardware_revision"],
        name=bridge["name"] or bridge["id"],
        sw_version=bridge["firmware_version"]["wifi"],
    )


class NotionEntity(CoordinatorEntity):
    """Define a base Notion entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        task_id: str,
        sensor_id: str,
        bridge_id: str,
        system_id: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        bridge = self.coordinator.data["bridges"].get(bridge_id, {})
        sensor = self.coordinator.data["sensors"][sensor_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sensor["hardware_id"])},
            manufacturer="Silicon Labs",
            model=sensor["hardware_revision"],
            name=str(sensor["name"]),
            sw_version=sensor["firmware_version"],
            via_device=(DOMAIN, bridge.get("hardware_id")),
        )

        self._attr_extra_state_attributes = {}
        self._attr_name = f'{sensor["name"]}: {description.name}'
        self._attr_unique_id = (
            f'{sensor_id}_{coordinator.data["tasks"][task_id]["task_type"]}'
        )
        self._bridge_id = bridge_id
        self._sensor_id = sensor_id
        self._system_id = system_id
        self._task_id = task_id
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self._task_id in self.coordinator.data["tasks"]
        )

    @callback
    def _async_update_bridge_id(self) -> None:
        """Update the entity's bridge ID if it has changed.

        Sensors can move to other bridges based on signal strength, etc.
        """
        sensor = self.coordinator.data["sensors"][self._sensor_id]

        # If the sensor's bridge ID is the same as what we had before or if it points
        # to a bridge that doesn't exist (which can happen due to a Notion API bug),
        # return immediately:
        if (
            self._bridge_id == sensor["bridge"]["id"]
            or sensor["bridge"]["id"] not in self.coordinator.data["bridges"]
        ):
            return

        self._bridge_id = sensor["bridge"]["id"]

        device_registry = dr.async_get(self.hass)
        this_device = device_registry.async_get_device(
            {(DOMAIN, sensor["hardware_id"])}
        )
        bridge = self.coordinator.data["bridges"][self._bridge_id]
        bridge_device = device_registry.async_get_device(
            {(DOMAIN, bridge["hardware_id"])}
        )

        if not bridge_device or not this_device:
            return

        device_registry.async_update_device(
            this_device.id, via_device_id=bridge_device.id
        )

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        """Respond to a DataUpdateCoordinator update."""
        if self._task_id in self.coordinator.data["tasks"]:
            self._async_update_bridge_id()
            self._async_update_from_latest_data()

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self._async_update_from_latest_data()
