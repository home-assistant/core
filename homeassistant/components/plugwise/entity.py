"""Generic Plugwise Entity Class."""
from __future__ import annotations

from homeassistant.const import ATTR_NAME, ATTR_VIA_DEVICE, CONF_HOST
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PlugwiseData, PlugwiseDataUpdateCoordinator


class PlugwiseEntity(CoordinatorEntity[PlugwiseData]):
    """Represent a PlugWise Entity."""

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialise the gateway."""
        super().__init__(coordinator)
        self._dev_id = device_id

        configuration_url: str | None = None
        if entry := self.coordinator.config_entry:
            configuration_url = f"http://{entry.data[CONF_HOST]}"

        data = coordinator.data.devices[device_id]
        self._attr_device_info = DeviceInfo(
            configuration_url=configuration_url,
            identifiers={(DOMAIN, device_id)},
            manufacturer=data.get("vendor"),
            model=data.get("model"),
            name=f"Smile {coordinator.data.gateway['smile_name']}",
            sw_version=data.get("fw"),
        )

        if device_id != coordinator.data.gateway["gateway_id"]:
            self._attr_device_info.update(
                {
                    ATTR_NAME: data.get("name"),
                    ATTR_VIA_DEVICE: (
                        DOMAIN,
                        str(self.coordinator.data.gateway["gateway_id"]),
                    ),
                }
            )

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self._handle_coordinator_update()
        await super().async_added_to_hass()
