"""Sensor component that handles additional ClimaCell data for your location."""
from __future__ import annotations

from abc import abstractmethod
import logging

from pyclimacell.const import CURRENT

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_API_VERSION, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import ClimaCellDataUpdateCoordinator, ClimaCellEntity
from .const import (
    CC_SENSOR_TYPES,
    CC_V3_SENSOR_TYPES,
    DOMAIN,
    ClimaCellSensorEntityDescription,
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
        api_class(hass, config_entry, coordinator, api_version, description)
        for description in sensor_types
    ]
    async_add_entities(entities)


class BaseClimaCellSensorEntity(ClimaCellEntity, SensorEntity):
    """Base ClimaCell sensor entity."""

    entity_description: ClimaCellSensorEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        coordinator: ClimaCellDataUpdateCoordinator,
        api_version: int,
        description: ClimaCellSensorEntityDescription,
    ) -> None:
        """Initialize ClimaCell Sensor Entity."""
        super().__init__(config_entry, coordinator, api_version)
        self.entity_description = description
        self._attr_entity_registry_enabled_default = False
        self._attr_name = f"{self._config_entry.data[CONF_NAME]} - {description.name}"
        self._attr_unique_id = (
            f"{self._config_entry.unique_id}_{slugify(description.name)}"
        )
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: self.attribution}
        self._attr_native_unit_of_measurement = (
            description.unit_metric
            if hass.config.units.is_metric
            else description.unit_imperial
        )

    @property
    @abstractmethod
    def _state(self) -> str | int | float | None:
        """Return the raw state."""

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state."""
        state = self._state
        if (
            state is not None
            and self.entity_description.unit_imperial is not None
            and self.entity_description.metric_conversion != 1.0
            and self.entity_description.is_metric_check is not None
            and self.hass.config.units.is_metric
            == self.entity_description.is_metric_check
        ):
            conversion = self.entity_description.metric_conversion
            # When conversion is a callable, we assume it's a single input function
            if callable(conversion):
                return round(conversion(state), 4)

            return round(state * conversion, 4)

        if self.entity_description.value_map is not None and state is not None:
            return self.entity_description.value_map(state).name.lower()

        return state


class ClimaCellSensorEntity(BaseClimaCellSensorEntity):
    """Sensor entity that talks to ClimaCell v4 API to retrieve non-weather data."""

    @property
    def _state(self) -> str | int | float | None:
        """Return the raw state."""
        return self._get_current_property(self.entity_description.key)


class ClimaCellV3SensorEntity(BaseClimaCellSensorEntity):
    """Sensor entity that talks to ClimaCell v3 API to retrieve non-weather data."""

    @property
    def _state(self) -> str | int | float | None:
        """Return the raw state."""
        return self._get_cc_value(
            self.coordinator.data[CURRENT], self.entity_description.key
        )
