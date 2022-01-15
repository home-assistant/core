"""Entity for the opengarage.io component."""

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN


class OpenGarageEntity(CoordinatorEntity):
    """Representation of a OpenGarage entity."""

    def __init__(self, open_garage_data_coordinator, device_id, description=None):
        """Initialize the entity."""
        super().__init__(open_garage_data_coordinator)

        if description is not None:
            self.entity_description = description
            self._attr_unique_id = f"{device_id}_{description.key}"
        else:
            self._attr_unique_id = device_id

        self._device_id = device_id
        self._update_attr()

    @callback
    def _update_attr(self) -> None:
        """Update the state and attributes."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr()
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return the device_info of the device."""
        device_info = DeviceInfo(
            configuration_url=self.coordinator.open_garage_connection.device_url,
            connections={(CONNECTION_NETWORK_MAC, self.coordinator.data["mac"])},
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Open Garage",
            name=self.coordinator.data["name"],
            suggested_area="Garage",
            sw_version=self.coordinator.data["fwv"],
        )
        return device_info
