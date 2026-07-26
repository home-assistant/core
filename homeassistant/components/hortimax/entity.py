"""Base entity for the Ridder HortiMaX Pro (HortOS) integration."""

from typing import override

from aiohortos import Readout

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import HortimaxCoordinator, source_key


class HortimaxEntity(CoordinatorEntity[HortimaxCoordinator]):
    """An entity backed by one readout of a HortOS source.

    HortOS data is two levels deep: controllers, and *sources* inside them
    (a weather station, a ventilation group, a valve group, ...). Each source
    becomes its own device, linked to its controller through ``via_device``.
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
            via_device=(DOMAIN, device_id),
        )

    @property
    def readout(self) -> Readout | None:
        """Return the current readout, or None once the controller drops it.

        Every known controller always has an entry in the coordinator data,
        but the readouts inside it come and go with what the controller
        reports.
        """
        return self.coordinator.data[self._device_id].readouts.get(self._key)

    @property
    @override
    def available(self) -> bool:
        """Return whether the readout is still being reported."""
        return super().available and self.readout is not None
