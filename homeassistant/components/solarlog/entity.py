"""Entities for SolarLog integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import (
    SolarLogBasicDataCoordinator,
    SolarLogDeviceDataCoordinator,
    SolarLogLongtimeDataCoordinator,
)


class SolarLogBasicCoordinatorEntity(CoordinatorEntity[SolarLogBasicDataCoordinator]):
    """Base SolarLog Coordinator entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarLogBasicDataCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the SolarLogBasicCoordinator sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            manufacturer="Solar-Log",
            model="Controller",
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="SolarLog",
            configuration_url=coordinator.solarlog.host,
        )
        self.entity_description = description


class SolarLogInverterEntity(CoordinatorEntity[SolarLogDeviceDataCoordinator]):
    """Base SolarLog inverter entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarLogDeviceDataCoordinator,
        description: SensorEntityDescription,
        device_id: int,
    ) -> None:
        """Initialize the SolarLogInverter sensor."""
        super().__init__(coordinator)
        name = f"{coordinator.config_entry.entry_id}_{slugify(coordinator.solarlog.device_name(device_id))}"
        self._attr_unique_id = f"{name}_{description.key}"
        self._attr_device_info = DeviceInfo(
            manufacturer="Solar-Log",
            model="Inverter",
            identifiers={(DOMAIN, name)},
            name=coordinator.solarlog.device_name(device_id),
            via_device=(DOMAIN, coordinator.config_entry.entry_id),
        )
        self.device_id = device_id
        self.entity_description = description


class SolarLogLongtimeCoordinatorEntity(
    CoordinatorEntity[SolarLogLongtimeDataCoordinator]
):
    """Base SolarLog Coordinator entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarLogLongtimeDataCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the SolarLogLongtimeCoordinator sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            manufacturer="Solar-Log",
            model="Controller",
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="SolarLog",
            configuration_url=coordinator.solarlog.host,
        )
        self.entity_description = description
