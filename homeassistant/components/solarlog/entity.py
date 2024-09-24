"""Entities for SolarLog integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import SolarLogCoordinator


class SolarLogBaseEntity(CoordinatorEntity[SolarLogCoordinator]):
    """SolarLog base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarLogCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the SolarLogCoordinator sensor."""
        super().__init__(coordinator)

        self.entity_description = description


class SolarLogCoordinatorEntity(SolarLogBaseEntity):
    """Base SolarLog Coordinator entity."""

    def __init__(
        self,
        coordinator: SolarLogCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the SolarLogCoordinator sensor."""
        super().__init__(coordinator, description)

        self._attr_unique_id = f"{coordinator.unique_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            manufacturer="Solar-Log",
            model="Controller",
            identifiers={(DOMAIN, coordinator.unique_id)},
            name=coordinator.name,
            configuration_url=coordinator.host,
        )


class SolarLogInverterEntity(SolarLogBaseEntity):
    """Base SolarLog inverter entity."""

    def __init__(
        self,
        coordinator: SolarLogCoordinator,
        description: SensorEntityDescription,
        device_id: int,
    ) -> None:
        """Initialize the SolarLogInverter sensor."""
        super().__init__(coordinator, description)
        name = f"{coordinator.unique_id}-{slugify(coordinator.solarlog.device_name(device_id))}"
        self._attr_unique_id = f"{name}-{description.key}"
        self._attr_device_info = DeviceInfo(
            manufacturer="Solar-Log",
            model="Inverter",
            identifiers={(DOMAIN, name)},
            name=coordinator.solarlog.device_name(device_id),
            via_device=(DOMAIN, coordinator.unique_id),
        )
        self.device_id = device_id
