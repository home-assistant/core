"""Support for monitoring OctoPrint binary sensors."""

from __future__ import annotations

from abc import abstractmethod

from pyoctoprintapi import OctoprintPrinterInfo

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OctoprintDataUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the available OctoPrint binary sensors."""
    coordinator: OctoprintDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["coordinator"]
    device_id = config_entry.unique_id

    assert device_id is not None

    entities: list[BinarySensorEntity] = [
        OctoPrintPrintingBinarySensor(coordinator, device_id),
        OctoPrintPrintingErrorBinarySensor(coordinator, device_id),
    ]

    async_add_entities(entities)


class OctoPrintBinarySensorBase(
    CoordinatorEntity[OctoprintDataUpdateCoordinator], BinarySensorEntity
):
    """Representation an OctoPrint binary sensor."""

    def __init__(
        self,
        coordinator: OctoprintDataUpdateCoordinator,
        sensor_type: str,
        device_id: str,
    ) -> None:
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_name = f"OctoPrint {sensor_type}"
        self._attr_unique_id = f"{sensor_type}-{device_id}"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self):
        """Return true if binary sensor is on."""
        if not (printer := self.coordinator.data["printer"]):
            return None

        return bool(self._get_flag_state(printer))

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data["printer"]

    @abstractmethod
    def _get_flag_state(self, printer_info: OctoprintPrinterInfo) -> bool | None:
        """Return the value of the sensor flag."""


class OctoPrintPrintingBinarySensor(OctoPrintBinarySensorBase):
    """Representation an OctoPrint binary sensor."""

    def __init__(
        self, coordinator: OctoprintDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, "Printing", device_id)

    def _get_flag_state(self, printer_info: OctoprintPrinterInfo) -> bool | None:
        return bool(printer_info.state.flags.printing)


class OctoPrintPrintingErrorBinarySensor(OctoPrintBinarySensorBase):
    """Representation an OctoPrint binary sensor."""

    def __init__(
        self, coordinator: OctoprintDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, "Printing Error", device_id)

    def _get_flag_state(self, printer_info: OctoprintPrinterInfo) -> bool | None:
        return bool(printer_info.state.flags.error)
