"""Generic Plugwise Entity Class."""

from __future__ import annotations

from plugwise import GwEntityData

from homeassistant.const import ATTR_NAME, ATTR_VIA_DEVICE, CONF_HOST
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    CONNECTION_ZIGBEE,
    DeviceInfo,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import AVAILABLE, DOMAIN
from .coordinator import PlugwiseDataUpdateCoordinator


class PlugwiseEntity(CoordinatorEntity[PlugwiseDataUpdateCoordinator]):
    """Represent a PlugWise Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialise the gateway."""
        super().__init__(coordinator)
        self._dev_id = device_id

        api = coordinator.api
        gateway_id = api.gateway_id
        entry = coordinator.config_entry

        # Link configuration-URL for the gateway device
        configuration_url = (
            f"http://{entry.data[CONF_HOST]}"
            if device_id == gateway_id and entry
            else None
        )

        # Build connections set
        connections = set()
        if mac := self.device.get("mac_address"):
            connections.add((CONNECTION_NETWORK_MAC, mac))
        if zigbee_mac := self.device.get("zigbee_mac_address"):
            connections.add((CONNECTION_ZIGBEE, zigbee_mac))

        # Set base device info
        self._attr_device_info = DeviceInfo(
            configuration_url=configuration_url,
            identifiers={(DOMAIN, device_id)},
            connections=connections,
            manufacturer=self.device.get("vendor"),
            model=self.device.get("model"),
            model_id=self.device.get("model_id"),
            name=api.smile.name,
            sw_version=self.device.get("firmware"),
            hw_version=self.device.get("hardware"),
        )

        # Add extra info if not the gateway device
        if device_id != gateway_id:
            self._attr_device_info.update(
                {
                    ATTR_NAME: self.device.get(ATTR_NAME),
                    ATTR_VIA_DEVICE: (DOMAIN, gateway_id),
                }
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self._dev_id in self.coordinator.data
            and (AVAILABLE not in self.device or self.device[AVAILABLE] is True)
            and super().available
        )

    @property
    def device(self) -> GwEntityData:
        """Return data for this device."""
        return self.coordinator.data[self._dev_id]
