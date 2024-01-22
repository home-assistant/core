"""Code to handle a Livisi Binary Sensor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LIVISI_STATE_CHANGE, LOGGER, WDS_DEVICE_TYPE
from .coordinator import LivisiDataUpdateCoordinator
from .entity import LivisiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary_sensor device."""
    coordinator: LivisiDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    @callback
    def handle_coordinator_update() -> None:
        """Add Window Sensor."""
        shc_devices: list[dict[str, Any]] = coordinator.data
        entities: list[BinarySensorEntity] = []
        for device in shc_devices:
            if device["id"] not in known_devices and device["type"] == WDS_DEVICE_TYPE:
                livisi_binary: BinarySensorEntity = LivisiWindowDoorSensor(
                    config_entry, coordinator, device
                )
                LOGGER.debug("Include device type: %s", device["type"])
                coordinator.devices.add(device["id"])
                known_devices.add(device["id"])
                entities.append(livisi_binary)
        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiBinarySensor(LivisiEntity, BinarySensorEntity):
    """Represents a Livisi Binary Sensor."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
        capability_name: str,
    ) -> None:
        """Initialize the Livisi sensor."""
        super().__init__(config_entry, coordinator, device)
        self._capability_id = self.capabilities[capability_name]

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self._capability_id}",
                self.update_states,
            )
        )

    @callback
    def update_states(self, state: bool) -> None:
        """Update the state of the device."""
        self._attr_is_on = state
        self.async_write_ha_state()


class LivisiWindowDoorSensor(LivisiBinarySensor):
    """Represents a Livisi Window/Door Sensor as a Binary Sensor Entity."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the Livisi window/door sensor."""
        super().__init__(config_entry, coordinator, device, "WindowDoorSensor")

        self._attr_device_class = (
            BinarySensorDeviceClass.DOOR
            if (device.get("tags", {}).get("typeCategory") == "TCDoorId")
            else BinarySensorDeviceClass.WINDOW
        )

    async def async_added_to_hass(self) -> None:
        """Get current state."""
        await super().async_added_to_hass()
        response = await self.coordinator.async_get_device_state(
            self._capability_id, "isOpen"
        )
        if response is None:
            self._attr_available = False
        else:
            self._attr_is_on = response
