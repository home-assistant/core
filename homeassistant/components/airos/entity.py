"""Generic AirOS Entity Class."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AIROS_DEVMODEL_KEY,
    AIROS_FWVERSION_KEY,
    AIROS_HOST_KEY,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import AirOSDataUpdateCoordinator


class AirOSEntity(CoordinatorEntity[AirOSDataUpdateCoordinator]):
    """Represent a AirOS Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirOSDataUpdateCoordinator,
    ) -> None:
        """Initialise the gateway."""
        super().__init__(coordinator)

        data = self.coordinator.data
        device_data = data.device_data
        host_data = device_data[AIROS_HOST_KEY]

        configuration_url: str | None = (
            f"https://{coordinator.config_entry.data[CONF_HOST]}"
        )

        self._attr_device_info = DeviceInfo(
            configuration_url=configuration_url,
            identifiers={(DOMAIN, str(data.device_id))},
            manufacturer=MANUFACTURER,
            model=host_data.get(AIROS_DEVMODEL_KEY),
            name=data.hostname,
            sw_version=host_data.get(AIROS_FWVERSION_KEY),
        )
