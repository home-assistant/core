"""Support for RainMachine devices."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RainMachineConfigEntry, RainMachineData
from .const import DATA_API_VERSIONS, DOMAIN
from .coordinator import RainMachineDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class RainMachineEntityDescription(EntityDescription):
    """Describe a RainMachine entity."""

    api_category: str


class RainMachineEntity(CoordinatorEntity[RainMachineDataUpdateCoordinator]):
    """Define a generic RainMachine entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: RainMachineConfigEntry,
        data: RainMachineData,
        description: RainMachineEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(data.coordinators[description.api_category])

        self._attr_extra_state_attributes = {}
        self._attr_unique_id = f"{data.controller.mac}_{description.key}"
        self._entry = entry
        self._data = data
        self._version_coordinator = data.coordinators[DATA_API_VERSIONS]
        self.entity_description = description

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this controller."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._data.controller.mac)},
            configuration_url=(
                f"https://{self._entry.data[CONF_IP_ADDRESS]}:"
                f"{self._entry.data[CONF_PORT]}"
            ),
            connections={(dr.CONNECTION_NETWORK_MAC, self._data.controller.mac)},
            name=self._data.controller.name.capitalize(),
            manufacturer="RainMachine",
            model=(
                f"Version {self._version_coordinator.data['hwVer']} "
                f"(API: {self._version_coordinator.data['apiVer']})"
            ),
            sw_version=self._version_coordinator.data["swVer"],
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Respond to a DataUpdateCoordinator update."""
        self.update_from_latest_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._version_coordinator.async_add_listener(
                self._handle_coordinator_update, self.coordinator_context
            )
        )
        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the state."""
