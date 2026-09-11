"""Base entity for the Ridder HortiMaX Pro (HortOS) integration."""

from typing import override

from aiohortos import Readout

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import HortimaxCoordinator, source_key


class HortimaxEntity(CoordinatorEntity[HortimaxCoordinator]):
    """An entity backed by one readout of a HortOS source.

    Sources (a weather station, a ventilation group, ...) each become their own
    device, linked to their controller through ``via_device_id``.
    """

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HortimaxCoordinator, device_id: str, key: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._key = key

        readout = coordinator.data[device_id].readouts[key]
        source = readout.source
        self._attr_unique_id = f"{device_id}::{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{device_id}::{source_key(source.type, source.name)}")
            },
            name=coordinator.data[device_id].source_names.get(
                source_key(source.type, source.name), source.display_name
            ),
            model=source.type,
            manufacturer=MANUFACTURER,
            via_device_id=dr.async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, device_id),
                config_entry_id=coordinator.config_entry.entry_id,
            ),
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the controller this readout belongs to is known."""
        return super().available and self._device_id in self.coordinator.data

    @property
    def readout(self) -> Readout | None:
        """Return the current readout, or None once the controller drops it.

        A reachable controller that stops reporting one readout leaves the
        entity unknown, not unavailable.
        """
        return self.coordinator.data[self._device_id].readouts.get(self._key)
