"""The PurpleAir integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiopurpleair.models.sensors import SensorModel

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_SHOW_ON_MAP
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PurpleAirConfigEntry, PurpleAirDataUpdateCoordinator

MANUFACTURER = "PurpleAir, Inc."


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
            manufacturer=MANUFACTURER,
            model=self.sensor_data.model,
            name=self.sensor_data.name,
            sw_version=self.sensor_data.firmware_version,
        )
        self._entry = entry

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity specific state attributes."""
        attrs: dict[str, Any] = {}
        if self.sensor_data.latitude is None or self.sensor_data.longitude is None:
            return attrs

        if self._entry.options.get(CONF_SHOW_ON_MAP):
            attrs[ATTR_LATITUDE] = self.sensor_data.latitude
            attrs[ATTR_LONGITUDE] = self.sensor_data.longitude
        else:
            # TODO: Do we really need to save the coordinates if mapping is False? # pylint: disable=fixme
            attrs["lati"] = self.sensor_data.latitude
            attrs["long"] = self.sensor_data.longitude
        return attrs

    @property
    def sensor_data(self) -> SensorModel:
        """Define a property to get this entity's SensorModel object."""
        return self.coordinator.data.data[self._sensor_index]
