"""Generic AirOS Entity Class."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirOSData, AirOSDataUpdateCoordinator


class AirOSEntity(CoordinatorEntity[AirOSDataUpdateCoordinator]):
    """Represent a AirOS Entity."""

    def __init__(
        self,
        coordinator: AirOSDataUpdateCoordinator,
    ) -> None:
        """Initialise the gateway."""
        super().__init__(coordinator)

        data = self.coordinator.data
        device_data = data.device_data
        host_data = device_data["host"]

        configuration_url: str | None = None
        if entry := self.coordinator.config_entry:
            configuration_url = f"https://{entry.data[CONF_HOST]}"

        self._attr_device_info = DeviceInfo(
            configuration_url=configuration_url,
            identifiers={(DOMAIN, str(data.device_id))},
            manufacturer="Ubiquiti",
            model=host_data.get("devmodel", "Unknown"),
            name=data.hostname,
            sw_version=host_data.get("fwversion", "Unknown"),
        )

    @property
    def _airdata(self) -> AirOSData:
        """Return the AirOS data."""
        return self.coordinator.data

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._airdata.device_id}_{self.entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self._handle_coordinator_update()
        await super().async_added_to_hass()
