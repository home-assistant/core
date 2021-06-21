"""Sensor component that handles additional ClimaCell data for your location."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
import logging
from typing import Any

from pyclimacell.const import CURRENT

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_NAME,
    CONF_API_VERSION,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import ClimaCellDataUpdateCoordinator, ClimaCellEntity
from .const import (
    ATTR_FIELD,
    ATTR_IS_METRIC_CHECK,
    ATTR_METRIC_CONVERSION,
    ATTR_VALUE_MAP,
    CC_SENSOR_TYPES,
    CC_V3_SENSOR_TYPES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    api_version = config_entry.data[CONF_API_VERSION]

    if api_version == 3:
        api_class = ClimaCellV3SensorEntity
        sensor_types = CC_V3_SENSOR_TYPES
    else:
        api_class = ClimaCellSensorEntity
        sensor_types = CC_SENSOR_TYPES
    entities = [
        api_class(config_entry, coordinator, api_version, sensor_type)
        for sensor_type in sensor_types
    ]
    async_add_entities(entities)


class BaseClimaCellSensorEntity(ClimaCellEntity, SensorEntity):
    """Base ClimaCell sensor entity."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: ClimaCellDataUpdateCoordinator,
        api_version: int,
        sensor_type: dict[str, str | float],
    ) -> None:
        """Initialize ClimaCell Sensor Entity."""
        super().__init__(config_entry, coordinator, api_version)
        self.sensor_type = sensor_type

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self._config_entry.data[CONF_NAME]} - {self.sensor_type[ATTR_NAME]}"

    @property
    def unique_id(self) -> str:
        """Return the unique id of the entity."""
        return f"{self._config_entry.unique_id}_{slugify(self.sensor_type[ATTR_NAME])}"

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        return {ATTR_ATTRIBUTION: self.attribution}

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if CONF_UNIT_OF_MEASUREMENT in self.sensor_type:
            return self.sensor_type[CONF_UNIT_OF_MEASUREMENT]

        if (
            CONF_UNIT_SYSTEM_IMPERIAL in self.sensor_type
            and CONF_UNIT_SYSTEM_METRIC in self.sensor_type
        ):
            if self.hass.config.units.is_metric:
                return self.sensor_type[CONF_UNIT_SYSTEM_METRIC]
            return self.sensor_type[CONF_UNIT_SYSTEM_IMPERIAL]

        return None

    @property
    @abstractmethod
    def _state(self) -> str | int | float | None:
        """Return the raw state."""

    @property
    def state(self) -> str | int | float | None:
        """Return the state."""
        if (
            self._state is not None
            and CONF_UNIT_SYSTEM_IMPERIAL in self.sensor_type
            and CONF_UNIT_SYSTEM_METRIC in self.sensor_type
            and ATTR_METRIC_CONVERSION in self.sensor_type
            and ATTR_IS_METRIC_CHECK in self.sensor_type
            and self.hass.config.units.is_metric
            == self.sensor_type[ATTR_IS_METRIC_CHECK]
        ):
            return round(self._state * self.sensor_type[ATTR_METRIC_CONVERSION], 4)

        if ATTR_VALUE_MAP in self.sensor_type and self._state is not None:
            return self.sensor_type[ATTR_VALUE_MAP](self._state).name.lower()
        return self._state


class ClimaCellSensorEntity(BaseClimaCellSensorEntity):
    """Sensor entity that talks to ClimaCell v4 API to retrieve non-weather data."""

    @property
    def _state(self) -> str | int | float | None:
        """Return the raw state."""
        return self._get_current_property(self.sensor_type[ATTR_FIELD])


class ClimaCellV3SensorEntity(BaseClimaCellSensorEntity):
    """Sensor entity that talks to ClimaCell v3 API to retrieve non-weather data."""

    @property
    def _state(self) -> str | int | float | None:
        """Return the raw state."""
        return self._get_cc_value(
            self.coordinator.data[CURRENT], self.sensor_type[ATTR_FIELD]
        )
