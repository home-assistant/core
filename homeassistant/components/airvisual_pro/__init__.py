"""The AirVisual Pro integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from pyairvisual import NodeSamba
from pyairvisual.node import NodeProError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, LOGGER

PLATFORMS = [Platform.SENSOR]

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AirVisual Pro from a config entry."""

    async def async_get_data() -> dict[str, Any]:
        """Get data from the device."""
        try:
            async with NodeSamba(
                entry.data[CONF_IP_ADDRESS], entry.data[CONF_PASSWORD]
            ) as node:
                return await node.async_get_latest_measurements()
        except NodeProError as err:
            raise UpdateFailed(f"Error while retrieving data: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name="Node/Pro data",
        update_interval=DEFAULT_UPDATE_INTERVAL,
        update_method=async_get_data,
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class AirVisualProEntity(CoordinatorEntity):
    """Define a generic AirVisual Pro entity."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, description: EntityDescription
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_extra_state_attributes = {}
        self._attr_unique_id = f"{coordinator.data['serial_number']}_{description.key}"
        self.entity_description = description

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data["serial_number"])},
            manufacturer="AirVisual",
            model=self.coordinator.data["status"]["model"],
            name=self.coordinator.data["settings"]["node_name"],
            hw_version=self.coordinator.data["status"]["system_version"],
            sw_version=self.coordinator.data["status"]["app_version"],
        )

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity's underlying data."""
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        """Respond to a DataUpdateCoordinator update."""
        self._async_update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self._async_update_from_latest_data()
