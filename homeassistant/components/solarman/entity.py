"""Base entity for the Solarman integration."""

from __future__ import annotations

from homeassistant.const import CONF_MODEL
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SN, DOMAIN, MODEL_NAME_MAP
from .coordinator import SolarmanDeviceUpdateCoordinator


class SolarmanEntity(CoordinatorEntity[SolarmanDeviceUpdateCoordinator]):
    """Defines a Solarman entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarmanDeviceUpdateCoordinator) -> None:
        """Initialize the Solarman entity."""
        super().__init__(coordinator)

        entry = coordinator.config_entry

        sn = entry.data[CONF_SN]
        model = entry.data[CONF_MODEL]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sn)},
            name=MODEL_NAME_MAP[model],
            manufacturer="SOLARMAN",
            model=model,
            serial_number=sn,
        )
