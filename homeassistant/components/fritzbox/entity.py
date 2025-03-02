"""Support for AVM FRITZ!SmartHome devices."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pyfritzhome import FritzhomeDevice
from pyfritzhome.devicetypes.fritzhomeentitybase import FritzhomeEntityBase

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FritzboxDataUpdateCoordinator


class FritzBoxEntity(CoordinatorEntity[FritzboxDataUpdateCoordinator], ABC):
    """Basis FritzBox entity."""

    def __init__(
        self,
        coordinator: FritzboxDataUpdateCoordinator,
        ain: str,
        entity_description: EntityDescription | None = None,
    ) -> None:
        """Initialize the FritzBox entity."""
        super().__init__(coordinator)

        self.ain = ain
        if entity_description is not None:
            self._attr_has_entity_name = True
            self.entity_description = entity_description
            self._attr_unique_id = f"{ain}_{entity_description.key}"
        else:
            self._attr_name = self.data.name
            self._attr_unique_id = ain

    @property
    @abstractmethod
    def data(self) -> FritzhomeEntityBase:
        """Return data object from coordinator."""


class FritzBoxDeviceEntity(FritzBoxEntity):
    """Reflects FritzhomeDevice and uses its attributes to construct FritzBoxDeviceEntity."""

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.data.present

    @property
    def data(self) -> FritzhomeDevice:
        """Return device data object from coordinator."""
        return self.coordinator.data.devices[self.ain]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return DeviceInfo(
            name=self.data.name,
            identifiers={(DOMAIN, self.ain)},
            manufacturer=self.data.manufacturer,
            model=self.data.productname,
            sw_version=self.data.fw_version,
            configuration_url=self.coordinator.configuration_url,
        )
