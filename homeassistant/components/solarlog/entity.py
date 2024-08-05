"""Entities for SolarLog integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import SolarLogCoordinator


class SolarLogCoordinatorEntity(CoordinatorEntity[SolarLogCoordinator]):
    """Base SolarLog Coordinator entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarLogCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the SolarLogCoordinator sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.unique_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            manufacturer="Solar-Log",
            model="Controller",
            identifiers={(DOMAIN, coordinator.unique_id)},
            name=coordinator.name,
            configuration_url=coordinator.host,
        )

        self.entity_description = description


class SolarLogInverterEntity(CoordinatorEntity[SolarLogCoordinator]):
    """Base SolarLog inverter entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolarLogCoordinator,
        description: SensorEntityDescription,
        device_id: int,
    ) -> None:
        """Initialize the SolarLogInverter sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id}-{slugify(coordinator.solarlog.device_name(device_id))}-{description.key}"
        self._attr_device_info = DeviceInfo(
            manufacturer="Solar-Log",
            model="Inverter",
            identifiers={
                (
                    DOMAIN,
                    f"{coordinator.unique_id}-{slugify(coordinator.solarlog.device_name(device_id))}",
                )
            },
            name=coordinator.solarlog.device_name(device_id),
            via_device=(DOMAIN, coordinator.unique_id),
        )
        self.entity_description = description
        self.device_id = device_id

    @property
    def available(self) -> bool:
        """Test if entity is available."""
        return super().available
