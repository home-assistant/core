"""Generic AirOS Entity Class."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_SSL
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import AirOSDataUpdateCoordinator


class AirOSEntity(CoordinatorEntity[AirOSDataUpdateCoordinator]):
    """Represent a AirOS Entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AirOSDataUpdateCoordinator) -> None:
        """Initialise the gateway."""
        super().__init__(coordinator)

        airos_data = self.coordinator.data
        url_schema = "https" if coordinator.config_entry.data[CONF_SSL] else "http"

        configuration_url: str | None = (
            f"{url_schema}://{coordinator.config_entry.data[CONF_HOST]}"
        )

        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, airos_data.derived.mac)},
            configuration_url=configuration_url,
            identifiers={(DOMAIN, str(airos_data.host.device_id))},
            manufacturer=MANUFACTURER,
            model=airos_data.host.devmodel,
            name=airos_data.host.hostname,
            sw_version=airos_data.host.fwversion,
        )
