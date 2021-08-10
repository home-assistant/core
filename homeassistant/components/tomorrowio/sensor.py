"""Sensor component that handles additional Tomorrowio data for your location."""
from __future__ import annotations

from abc import abstractmethod
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import TomorrowioDataUpdateCoordinator, TomorrowioEntity
from .const import CC_SENSOR_TYPES, DOMAIN, TomorrowioSensorEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = [
        TomorrowioSensorEntity(hass, config_entry, coordinator, 4, description)
        for description in CC_SENSOR_TYPES
    ]
    async_add_entities(entities)


class BaseTomorrowioSensorEntity(TomorrowioEntity, SensorEntity):
    """Base Tomorrow.io sensor entity."""

    entity_description: TomorrowioSensorEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        coordinator: TomorrowioDataUpdateCoordinator,
        api_version: int,
        description: TomorrowioSensorEntityDescription,
    ) -> None:
        """Initialize Tomorrow.io Sensor Entity."""
        super().__init__(config_entry, coordinator, api_version)
        self.entity_description = description
        self._attr_entity_registry_enabled_default = False
        self._attr_name = f"{self._config_entry.data[CONF_NAME]} - {description.name}"
        self._attr_unique_id = (
            f"{self._config_entry.unique_id}_{slugify(description.name)}"
        )
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: self.attribution}
        self._attr_unit_of_measurement = (
            description.unit_metric
            if hass.config.units.is_metric
            else description.unit_imperial
        )

    @property
    @abstractmethod
    def _state(self) -> str | int | float | None:
        """Return the raw state."""

    @property
    def state(self) -> str | int | float | None:
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
                return round(conversion(float(state)), 4)

            return round(float(state) * conversion, 4)

        if self.entity_description.value_map is not None and state is not None:
            return self.entity_description.value_map(state).name.lower()

        return state


class TomorrowioSensorEntity(BaseTomorrowioSensorEntity):
    """Sensor entity that talks to Tomorrow.io v4 API to retrieve non-weather data."""

    @property
    def _state(self) -> str | int | float | None:
        """Return the raw state."""
        return self._get_current_property(self.entity_description.key)
