"""The PurpleAir integration."""

from collections.abc import Mapping
from typing import Any, override

from aiopurpleair.models.sensors import SensorModel

from homeassistant.const import CONF_SHOW_ON_MAP, EntityStateAttribute
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PurpleAirConfigEntry, PurpleAirDataUpdateCoordinator


class PurpleAirEntity(CoordinatorEntity[PurpleAirDataUpdateCoordinator]):
    """Define a base PurpleAir entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: PurpleAirConfigEntry,
        sensor_index: int,
    ) -> None:
        """Initialize."""
        super().__init__(entry.runtime_data)

        self._sensor_index = sensor_index

        self._attr_device_info = DeviceInfo(
            configuration_url=self.coordinator.async_get_map_url(sensor_index),
            hw_version=self.sensor_data.hardware,
            identifiers={(DOMAIN, str(sensor_index))},
            manufacturer="PurpleAir, Inc.",
            model=self.sensor_data.model,
            name=self.sensor_data.name,
            sw_version=self.sensor_data.firmware_version,
        )
        self._entry = entry

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity specific state attributes."""
        attrs: dict[str, Any] = {}

        # Displaying the geography on the map relies upon putting the latitude/longitude
        # in the entity attributes with "latitude" and "longitude" as the keys.
        # Conversely, we can hide the location on the map by using other keys, like
        # "lati" and "long":
        if self._entry.options.get(CONF_SHOW_ON_MAP):
            attrs[EntityStateAttribute.LATITUDE] = self.sensor_data.latitude
            attrs[EntityStateAttribute.LONGITUDE] = self.sensor_data.longitude
        else:
            attrs["lati"] = self.sensor_data.latitude
            attrs["long"] = self.sensor_data.longitude
        return attrs

    @property
    def sensor_data(self) -> SensorModel:
        """Define a property to get this entity's SensorModel object."""
        return self.coordinator.data.data[self._sensor_index]
