"""Generic AirOS Entity Class."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_SSL
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, SECTION_ADVANCED_SETTINGS
from .coordinator import AirOSDataUpdateCoordinator


class AirOSEntity(CoordinatorEntity[AirOSDataUpdateCoordinator]):
    """Represent a AirOS Entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AirOSDataUpdateCoordinator) -> None:
        """Initialise the gateway."""
        super().__init__(coordinator)

        airos_data = self.coordinator.data
        url_schema = (
            "https"
            if coordinator.config_entry.data[SECTION_ADVANCED_SETTINGS][CONF_SSL]
            else "http"
        )

        configuration_url: str | None = (
            f"{url_schema}://{coordinator.config_entry.data[CONF_HOST]}"
        )

        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, airos_data.derived.mac)},
            configuration_url=configuration_url,
            identifiers={(DOMAIN, airos_data.derived.mac)},
            manufacturer=MANUFACTURER,
            model=airos_data.host.devmodel,
            model_id=(
                sku
                if (sku := airos_data.derived.sku) not in ["UNKNOWN", "AMBIGUOUS"]
                else None
            ),
            name=airos_data.host.hostname,
            sw_version=airos_data.host.fwversion,
        )
