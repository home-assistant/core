"""Calculates mold growth indication from temperature and humidity."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import logging
import math
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant import util
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_UNIQUE_ID,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device import async_entity_id_to_device
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.unit_conversion import TemperatureConverter
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import (
    CONF_CALIBRATION_FACTOR,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_TEMP,
    DEFAULT_NAME,
)

_LOGGER = logging.getLogger(__name__)

ATTR_CRITICAL_TEMP = "estimated_critical_temp"
ATTR_DEWPOINT = "dewpoint"


MAGNUS_K2 = 17.62
MAGNUS_K3 = 243.12

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_INDOOR_TEMP): cv.entity_id,
        vol.Required(CONF_OUTDOOR_TEMP): cv.entity_id,
        vol.Required(CONF_INDOOR_HUMIDITY): cv.entity_id,
        vol.Optional(CONF_CALIBRATION_FACTOR): vol.Coerce(float),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up MoldIndicator sensor."""
    name: str = config.get(CONF_NAME, DEFAULT_NAME)
    indoor_temp_sensor: str = config[CONF_INDOOR_TEMP]
    outdoor_temp_sensor: str = config[CONF_OUTDOOR_TEMP]
    indoor_humidity_sensor: str = config[CONF_INDOOR_HUMIDITY]
    calib_factor: float = config[CONF_CALIBRATION_FACTOR]
    unique_id: str | None = config.get(CONF_UNIQUE_ID)

    async_add_entities(
        [
            MoldIndicator(
                hass,
                name,
                hass.config.units is METRIC_SYSTEM,
                indoor_temp_sensor,
                outdoor_temp_sensor,
                indoor_humidity_sensor,
                calib_factor,
                unique_id,
            )
        ],
        False,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Mold indicator sensor entry."""
    name: str = entry.options[CONF_NAME]
    indoor_temp_sensor: str = entry.options[CONF_INDOOR_TEMP]
    outdoor_temp_sensor: str = entry.options[CONF_OUTDOOR_TEMP]
    indoor_humidity_sensor: str = entry.options[CONF_INDOOR_HUMIDITY]
    calib_factor: float = entry.options[CONF_CALIBRATION_FACTOR]

    async_add_entities(
        [
            MoldIndicator(
                hass,
                name,
                hass.config.units is METRIC_SYSTEM,
                indoor_temp_sensor,
                outdoor_temp_sensor,
                indoor_humidity_sensor,
                calib_factor,
                entry.entry_id,
            )
        ],
        False,
    )


class MoldIndicator(SensorEntity):
    """Represents a MoldIndication sensor."""

    _attr_should_poll = False
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        is_metric: bool,
        indoor_temp_sensor: str,
        outdoor_temp_sensor: str,
        indoor_humidity_sensor: str,
        calib_factor: float,
        unique_id: str | None,
    ) -> None:
        """Initialize the sensor."""
        self._attr_name = name
        self._attr_unique_id = unique_id

        self._entities = {
            CONF_INDOOR_TEMP: indoor_temp_sensor,
            CONF_OUTDOOR_TEMP: outdoor_temp_sensor,
            CONF_INDOOR_HUMIDITY: indoor_humidity_sensor,
        }
        self._calib_factor = calib_factor
        self._is_metric = is_metric
        self._attr_available = False
        self._dewpoint: float | None = None
        self._indoor_temp: float | None = None
        self._outdoor_temp: float | None = None
        self._indoor_hum: float | None = None
        self._crit_temp: float | None = None
        if indoor_humidity_sensor:
            self.device_entry = async_entity_id_to_device(
                hass,
                indoor_humidity_sensor,
            )
        self._preview_callback: Callable[[str, Mapping[str, Any]], None] | None = None

    @callback
    def async_start_preview(
        self,
        preview_callback: Callable[[str, Mapping[str, Any]], None],
    ) -> CALLBACK_TYPE:
        """Render a preview."""
        # Abort early if there is no source entity_id's or calibration factor
        if not all((*self._entities.values(), self._calib_factor)):
            self._attr_available = False
            calculated_state = self._async_calculate_state()
            preview_callback(calculated_state.state, calculated_state.attributes)
            return self._call_on_remove_callbacks

        self._preview_callback = preview_callback

        self._async_setup_sensor()
        return self._call_on_remove_callbacks

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self._async_setup_sensor()

    @callback
    def _async_setup_sensor(self) -> None:
        """Set up the sensor and start tracking state changes."""

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._entities.values(),
                self._async_mold_indicator_sensor_state_listener,
            )
        )

        # Replay current state of source entities
        for entity_id in self._entities.values():
            state = self.hass.states.get(entity_id)
            state_event: Event[EventStateChangedData] = Event(
                "", {"entity_id": entity_id, "new_state": state, "old_state": None}
            )
            self._async_mold_indicator_sensor_state_listener(
                state_event, update_state=False
            )

        self._recalculate()

        if self._preview_callback:
            calculated_state = self._async_calculate_state()
            self._preview_callback(calculated_state.state, calculated_state.attributes)

    @callback
    def _async_mold_indicator_sensor_state_listener(
        self, event: Event[EventStateChangedData], update_state: bool = True
    ) -> None:
        """Handle state changes for dependent sensors."""
        entity_id = event.data["entity_id"]
        new_state = event.data["new_state"]

        _LOGGER.debug(
            "Sensor state change for %s that had old state %s and new state %s",
            entity_id,
            event.data["old_state"],
            new_state,
        )

        # update state depending on which sensor changed
        if entity_id == self._entities[CONF_INDOOR_TEMP]:
            self._indoor_temp = self._get_temperature_from_state(new_state)
        elif entity_id == self._entities[CONF_OUTDOOR_TEMP]:
            self._outdoor_temp = self._get_temperature_from_state(new_state)
        elif entity_id == self._entities[CONF_INDOOR_HUMIDITY]:
            self._indoor_hum = self._get_humidity_from_state(new_state)

        if not update_state:
            return

        self._recalculate()

        if self._preview_callback:
            calculated_state = self._async_calculate_state()
            self._preview_callback(calculated_state.state, calculated_state.attributes)
        # only write state to the state machine if we are not in preview mode
        else:
            self.async_write_ha_state()

    @callback
    def _recalculate(self) -> None:
        """Recalculate mold indicator from cached sensor values."""
        # Check if all sensors are available
        if None in (self._indoor_temp, self._indoor_hum, self._outdoor_temp):
            self._attr_available = False
            self._attr_native_value = None
            self._dewpoint = None
            self._crit_temp = None
            return

        # Calculate dewpoint and mold indicator
        self._calc_dewpoint()
        self._calc_moldindicator()
        self._attr_available = self._attr_native_value is not None

    def _get_value_from_state(
        self,
        state: State | None,
        validator: Callable[[float, str | None], float | None],
    ) -> float | None:
        """Get and validate a sensor value from state."""
        if state is None:
            return None

        if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            _LOGGER.debug(
                "Unable to get sensor %s, state: %s",
                state.entity_id,
                state.state,
            )
            return None

        if (value := util.convert(state.state, float)) is None:
            _LOGGER.debug(
                "Unable to parse sensor value %s, state: %s to float",
                state.entity_id,
                state.state,
            )
            return None

        return validator(value, state.attributes.get(ATTR_UNIT_OF_MEASUREMENT))

    def _get_temperature_from_state(self, state: State | None) -> float | None:
        """Get temperature value in Celsius from state."""

        def validate_temperature(value: float, unit: str | None) -> float | None:
            if TYPE_CHECKING:
                assert state is not None

            if unit not in UnitOfTemperature:
                _LOGGER.warning(
                    "Temp sensor %s has unsupported unit: %s (allowed: %s, %s)",
                    state.entity_id,
                    unit,
                    UnitOfTemperature.CELSIUS,
                    UnitOfTemperature.FAHRENHEIT,
                )
                return None
            return TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)

        return self._get_value_from_state(state, validate_temperature)

    def _get_humidity_from_state(self, state: State | None) -> float | None:
        """Get humidity value from state."""

        def validate_humidity(value: float, unit: str | None) -> float | None:
            if TYPE_CHECKING:
                assert state is not None

            if unit != PERCENTAGE:
                _LOGGER.warning(
                    "Humidity sensor %s has unsupported unit: %s (allowed: %s)",
                    state.entity_id,
                    unit,
                    PERCENTAGE,
                )
                return None
            if not 0 <= value <= 100:
                _LOGGER.warning(
                    "Humidity sensor %s is out of range: %s (allowed: 0-100)",
                    state.entity_id,
                    value,
                )
                return None
            return value

        return self._get_value_from_state(state, validate_humidity)

    def _calc_dewpoint(self) -> None:
        """Calculate the dewpoint for the indoor air."""
        # Use magnus approximation to calculate the dew point
        if TYPE_CHECKING:
            assert self._indoor_temp and self._indoor_hum
        alpha = MAGNUS_K2 * self._indoor_temp / (MAGNUS_K3 + self._indoor_temp)
        beta = MAGNUS_K2 * MAGNUS_K3 / (MAGNUS_K3 + self._indoor_temp)

        if self._indoor_hum == 0:
            self._dewpoint = -50  # not defined, assume very low value
        else:
            self._dewpoint = (
                MAGNUS_K3
                * (alpha + math.log(self._indoor_hum / 100.0))
                / (beta - math.log(self._indoor_hum / 100.0))
            )
        _LOGGER.debug("Dewpoint: %f %s", self._dewpoint, UnitOfTemperature.CELSIUS)

    def _calc_moldindicator(self) -> None:
        """Calculate the mold indicator value."""
        if TYPE_CHECKING:
            assert self._outdoor_temp and self._indoor_temp and self._dewpoint

        if None in (self._dewpoint, self._calib_factor) or self._calib_factor == 0:
            _LOGGER.debug(
                "Invalid inputs - dewpoint: %s, calibration-factor: %s",
                self._dewpoint,
                self._calib_factor,
            )
            self._attr_native_value = None
            self._crit_temp = None
            return

        # first calculate the approximate temperature at the calibration point
        self._crit_temp = (
            self._outdoor_temp
            + (self._indoor_temp - self._outdoor_temp) / self._calib_factor
        )

        _LOGGER.debug(
            "Estimated Critical Temperature: %f %s",
            self._crit_temp,
            UnitOfTemperature.CELSIUS,
        )

        # Then calculate the humidity at this point
        alpha = MAGNUS_K2 * self._crit_temp / (MAGNUS_K3 + self._crit_temp)
        beta = MAGNUS_K2 * MAGNUS_K3 / (MAGNUS_K3 + self._crit_temp)

        crit_humidity = (
            math.exp(
                (self._dewpoint * beta - MAGNUS_K3 * alpha)
                / (self._dewpoint + MAGNUS_K3)
            )
            * 100.0
        )

        # check bounds and format
        if crit_humidity > 100:
            self._attr_native_value = 100
        elif crit_humidity < 0:
            self._attr_native_value = 0
        else:
            self._attr_native_value = int(crit_humidity)

        _LOGGER.debug("Mold indicator humidity: %s", self.native_value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self._is_metric:
            convert_to = UnitOfTemperature.CELSIUS
        else:
            convert_to = UnitOfTemperature.FAHRENHEIT

        dewpoint = (
            TemperatureConverter.convert(
                self._dewpoint, UnitOfTemperature.CELSIUS, convert_to
            )
            if self._dewpoint is not None
            else None
        )

        crit_temp = (
            TemperatureConverter.convert(
                self._crit_temp, UnitOfTemperature.CELSIUS, convert_to
            )
            if self._crit_temp is not None
            else None
        )

        return {
            ATTR_DEWPOINT: round(dewpoint, 2) if dewpoint else None,
            ATTR_CRITICAL_TEMP: round(crit_temp, 2) if crit_temp else None,
        }
