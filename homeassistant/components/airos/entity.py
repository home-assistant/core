"""Generic AirOS Entity Class."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import AirOSData, AirOSDataUpdateCoordinator


class AirOSEntity(CoordinatorEntity[AirOSDataUpdateCoordinator]):
    """Represent a AirOS Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirOSDataUpdateCoordinator,
    ) -> None:
        """Initialise the gateway."""
        super().__init__(coordinator)

        airos_data: AirOSData = self.coordinator.data

        configuration_url: str | None = (
            f"https://{coordinator.config_entry.data[CONF_HOST]}"
        )

        self._attr_device_info = DeviceInfo(
            configuration_url=configuration_url,
            identifiers={(DOMAIN, str(airos_data.host.device_id))},
            manufacturer=MANUFACTURER,
            model=airos_data.host.devmodel,
            name=airos_data.host.hostname,
            sw_version=airos_data.host.fwversion,
        )
