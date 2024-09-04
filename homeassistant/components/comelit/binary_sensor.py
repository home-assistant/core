"""Support for sensors."""

from __future__ import annotations

from aiocomelit import ComelitVedoZoneObject
from aiocomelit.const import ALARM_ZONES

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ComelitVedoSystem


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comelit VEDO presence sensors."""

    coordinator: ComelitVedoSystem = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        ComelitVedoBinarySensorEntity(coordinator, device, config_entry.entry_id)
        for device in coordinator.data[ALARM_ZONES].values()
    )


class ComelitVedoBinarySensorEntity(
    CoordinatorEntity[ComelitVedoSystem], BinarySensorEntity
):
    """Sensor device."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(
        self,
        coordinator: ComelitVedoSystem,
        zone: ComelitVedoZoneObject,
        config_entry_entry_id: str,
    ) -> None:
        """Init sensor entity."""
        self._api = coordinator.api
        self._zone = zone
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-presence-{zone.index}"
        self._attr_device_info = coordinator.platform_device_info(zone, "zone")

    @property
    def is_on(self) -> bool:
        """Presence detected."""
        return self.coordinator.data[ALARM_ZONES][self._zone.index].status_api == "0001"
