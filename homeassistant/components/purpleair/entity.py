"""PurpleAir entities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from aiopurpleair.models.sensors import SensorModel

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_SHOW_ON_MAP
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PurpleAirConfigEntry, PurpleAirDataUpdateCoordinator

MANUFACTURER: Final[str] = "PurpleAir, Inc."


class PurpleAirEntity(CoordinatorEntity[PurpleAirDataUpdateCoordinator]):
    """Entity."""

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
        """Get extra state attributes."""
        attrs: dict[str, Any] = {}
        # TODO: aiopurpleair crashes with null coordinates, fix required else this code cannot get test coverage # pylint: disable=fixme
        # See: https://github.com/bachya/aiopurpleair/issues/573
        if self.sensor_data.latitude is None or self.sensor_data.longitude is None:
            return attrs

        if self._entry.options.get(CONF_SHOW_ON_MAP) is True:
            attrs[ATTR_LATITUDE] = self.sensor_data.latitude
            attrs[ATTR_LONGITUDE] = self.sensor_data.longitude

        return attrs

    @property
    def sensor_data(self) -> SensorModel:
        """Get SensorModel object."""
        return self.coordinator.data.data[self._sensor_index]
