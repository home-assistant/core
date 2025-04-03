"""Shelly Light integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ShellyCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Shelly lights from config entry."""
    coordinator: ShellyCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create light entities for all discovered devices
    async_add_entities(
        ShellyLight(coordinator, device_id)
        for device_id in coordinator.devices
        if coordinator.is_light_device(device_id)
    )

    # Register callback for new devices
    config_entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: _async_discover_new_devices(hass, coordinator, async_add_entities)
        )
    )


@callback
def _async_discover_new_devices(
    hass: HomeAssistant,
    coordinator: ShellyCoordinator,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Discover and add new devices."""
    new_entities = []
    for device_id in coordinator.devices:
        if device_id not in coordinator.added_devices and coordinator.is_light_device(
            device_id
        ):
            new_entities.append(ShellyLight(coordinator, device_id))
            coordinator.added_devices.add(device_id)

    if new_entities:
        async_add_entities(new_entities)


class ShellyLight(CoordinatorEntity[ShellyCoordinator], LightEntity):
    """Representation of a Shelly light."""

    def __init__(self, coordinator: ShellyCoordinator, device_id: str) -> None:
        """Initialize the Shelly light."""
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_name = f"Shelly {device_id}"
        self._attr_unique_id = f"shelly_{device_id}"
        self._available = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for automatic registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name=self._attr_name,
            manufacturer="Shelly",
            model=self.coordinator.devices[self.device_id].get(
                "model", "Unknown Shelly"
            ),
            configuration_url=f"http://{self.coordinator.devices[self.device_id]['host']}",
        )

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.coordinator.devices[self.device_id]["state"]

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        return self.coordinator.devices[self.device_id].get("brightness")

    @property
    def available(self) -> bool:
        """Return if light is available."""
        return self._available and self.device_id in self.coordinator.devices

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on a Shelly device."""

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.device_id not in self.coordinator.devices:
            self._available = False
            self.async_write_ha_state()
            return

        device_data = self.coordinator.devices[self.device_id]

        if not self._available and device_data["online"]:
            self._available = True

        if any(
            [
                self.is_on != device_data["state"],
                self.brightness != device_data.get("brightness"),
                self.available != (device_data["online"] and self._available),
            ]
        ):
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
