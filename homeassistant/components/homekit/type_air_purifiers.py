"""Class to hold all air purifier accessories."""

import logging
from typing import Any

from pyhap.characteristic import Characteristic
from pyhap.const import CATEGORY_AIR_PURIFIER
from pyhap.service import Service
from pyhap.util import callback as pyhap_callback

from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HassJobType,
    State,
    callback,
)
from homeassistant.helpers.event import async_track_state_change_event

from .accessories import TYPES
from .const import (
    CHAR_ACTIVE,
    CHAR_AIR_QUALITY,
    CHAR_CURRENT_AIR_PURIFIER_STATE,
    CHAR_CURRENT_HUMIDITY,
    CHAR_CURRENT_TEMPERATURE,
    CHAR_FILTER_CHANGE_INDICATION,
    CHAR_FILTER_LIFE_LEVEL,
    CHAR_NAME,
    CHAR_PM25_DENSITY,
    CHAR_TARGET_AIR_PURIFIER_STATE,
    CONF_LINKED_FILTER_CHANGE_INDICATION,
    CONF_LINKED_FILTER_LIFE_LEVEL,
    CONF_LINKED_HUMIDITY_SENSOR,
    CONF_LINKED_PM25_SENSOR,
    CONF_LINKED_TEMPERATURE_SENSOR,
    SERV_AIR_PURIFIER,
    SERV_AIR_QUALITY_SENSOR,
    SERV_FILTER_MAINTENANCE,
    SERV_HUMIDITY_SENSOR,
    SERV_TEMPERATURE_SENSOR,
    THRESHOLD_FILTER_CHANGE_NEEDED,
)
from .type_fans import ATTR_PRESET_MODE, CHAR_ROTATION_SPEED, Fan
from .util import cleanup_name_for_homekit, convert_to_float, density_to_air_quality

_LOGGER = logging.getLogger(__name__)

CURRENT_STATE_INACTIVE = 0
CURRENT_STATE_IDLE = 1
CURRENT_STATE_PURIFYING_AIR = 2
TARGET_STATE_MANUAL = 0
TARGET_STATE_AUTO = 1
FILTER_CHANGE_FILTER = 1
FILTER_OK = 0

IGNORED_STATES = {STATE_UNAVAILABLE, STATE_UNKNOWN}


@TYPES.register("AirPurifier")
class AirPurifier(Fan):
    """Generate an AirPurifier accessory for an air purifier entity.

    Currently supports, in addition to Fan properties:
    temperature; humidity; PM2.5; auto mode.
    """

    def __init__(self, *args: Any) -> None:
        """Initialize a new AirPurifier accessory object."""
        super().__init__(*args, category=CATEGORY_AIR_PURIFIER)

        self.auto_preset: str | None = None
        if self.preset_modes is not None:
            for preset in self.preset_modes:
                if str(preset).lower() == "auto":
                    self.auto_preset = preset
                    break

    def create_services(self) -> Service:
        """Create and configure the primary service for this accessory."""
        self.chars.append(CHAR_ACTIVE)
        self.chars.append(CHAR_CURRENT_AIR_PURIFIER_STATE)
        self.chars.append(CHAR_TARGET_AIR_PURIFIER_STATE)
        serv_air_purifier = self.add_preload_service(SERV_AIR_PURIFIER, self.chars)
        self.set_primary_service(serv_air_purifier)

        self.char_active: Characteristic = serv_air_purifier.configure_char(
            CHAR_ACTIVE, value=0
        )

        self.preset_mode_chars: dict[str, Characteristic]
        self.char_current_humidity: Characteristic | None = None
        self.char_pm25_density: Characteristic | None = None
        self.char_current_temperature: Characteristic | None = None
        self.char_filter_change_indication: Characteristic | None = None
        self.char_filter_life_level: Characteristic | None = None

        self.char_target_air_purifier_state: Characteristic = (
            serv_air_purifier.configure_char(
                CHAR_TARGET_AIR_PURIFIER_STATE,
                value=0,
            )
        )

        self.char_current_air_purifier_state: Characteristic = (
            serv_air_purifier.configure_char(
                CHAR_CURRENT_AIR_PURIFIER_STATE,
                value=0,
            )
        )

        self.linked_humidity_sensor = self.config.get(CONF_LINKED_HUMIDITY_SENSOR)
        if self.linked_humidity_sensor:
            humidity_serv = self.add_preload_service(SERV_HUMIDITY_SENSOR, CHAR_NAME)
            serv_air_purifier.add_linked_service(humidity_serv)
            self.char_current_humidity = humidity_serv.configure_char(
                CHAR_CURRENT_HUMIDITY, value=0
            )

            humidity_state = self.hass.states.get(self.linked_humidity_sensor)
            if humidity_state:
                self._async_update_current_humidity(humidity_state)

        self.linked_pm25_sensor = self.config.get(CONF_LINKED_PM25_SENSOR)
        if self.linked_pm25_sensor:
            pm25_serv = self.add_preload_service(
                SERV_AIR_QUALITY_SENSOR,
                [CHAR_AIR_QUALITY, CHAR_NAME, CHAR_PM25_DENSITY],
            )
            serv_air_purifier.add_linked_service(pm25_serv)
            self.char_pm25_density = pm25_serv.configure_char(
                CHAR_PM25_DENSITY, value=0
            )

            self.char_air_quality = pm25_serv.configure_char(CHAR_AIR_QUALITY)

            pm25_state = self.hass.states.get(self.linked_pm25_sensor)
            if pm25_state:
                self._async_update_current_pm25(pm25_state)

        self.linked_temperature_sensor = self.config.get(CONF_LINKED_TEMPERATURE_SENSOR)
        if self.linked_temperature_sensor:
            temperature_serv = self.add_preload_service(
                SERV_TEMPERATURE_SENSOR, [CHAR_NAME, CHAR_CURRENT_TEMPERATURE]
            )
            serv_air_purifier.add_linked_service(temperature_serv)
            self.char_current_temperature = temperature_serv.configure_char(
                CHAR_CURRENT_TEMPERATURE, value=0
            )

            temperature_state = self.hass.states.get(self.linked_temperature_sensor)
            if temperature_state:
                self._async_update_current_temperature(temperature_state)

        self.linked_filter_change_indicator_binary_sensor = self.config.get(
            CONF_LINKED_FILTER_CHANGE_INDICATION
        )
        self.linked_filter_life_level_sensor = self.config.get(
            CONF_LINKED_FILTER_LIFE_LEVEL
        )
        if (
            self.linked_filter_change_indicator_binary_sensor
            or self.linked_filter_life_level_sensor
        ):
            chars = [CHAR_NAME, CHAR_FILTER_CHANGE_INDICATION]
            if self.linked_filter_life_level_sensor:
                chars.append(CHAR_FILTER_LIFE_LEVEL)
            serv_filter_maintenance = self.add_preload_service(
                SERV_FILTER_MAINTENANCE, chars
            )
            serv_air_purifier.add_linked_service(serv_filter_maintenance)
            serv_filter_maintenance.configure_char(
                CHAR_NAME,
                value=cleanup_name_for_homekit(f"{self.display_name} Filter"),
            )

            self.char_filter_change_indication = serv_filter_maintenance.configure_char(
                CHAR_FILTER_CHANGE_INDICATION,
                value=0,
            )

            if self.linked_filter_change_indicator_binary_sensor:
                filter_change_indicator_state = self.hass.states.get(
                    self.linked_filter_change_indicator_binary_sensor
                )
                if filter_change_indicator_state:
                    self._async_update_filter_change_indicator(
                        filter_change_indicator_state
                    )

            if self.linked_filter_life_level_sensor:
                self.char_filter_life_level = serv_filter_maintenance.configure_char(
                    CHAR_FILTER_LIFE_LEVEL,
                    value=0,
                )

                filter_life_level_state = self.hass.states.get(
                    self.linked_filter_life_level_sensor
                )
                if filter_life_level_state:
                    self._async_update_filter_life_level(filter_life_level_state)

        return serv_air_purifier

    def should_add_preset_mode_switch(self, preset_mode: str) -> bool:
        """Check if a preset mode switch should be added."""
        return preset_mode.lower() != "auto"

    @callback
    @pyhap_callback  # type: ignore[misc]
    def run(self) -> None:
        """Handle accessory driver started event.

        Run inside the Home Assistant event loop.
        """
        if self.linked_humidity_sensor:
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass,
                    [self.linked_humidity_sensor],
                    self._async_update_current_humidity_event,
                    job_type=HassJobType.Callback,
                )
            )

        if self.linked_pm25_sensor:
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass,
                    [self.linked_pm25_sensor],
                    self._async_update_current_pm25_event,
                    job_type=HassJobType.Callback,
                )
            )

        if self.linked_temperature_sensor:
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass,
                    [self.linked_temperature_sensor],
                    self._async_update_current_temperature_event,
                    job_type=HassJobType.Callback,
                )
            )

        if self.linked_filter_change_indicator_binary_sensor:
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass,
                    [self.linked_filter_change_indicator_binary_sensor],
                    self._async_update_filter_change_indicator_event,
                    job_type=HassJobType.Callback,
                )
            )

        if self.linked_filter_life_level_sensor:
            self._subscriptions.append(
                async_track_state_change_event(
                    self.hass,
                    [self.linked_filter_life_level_sensor],
                    self._async_update_filter_life_level_event,
                    job_type=HassJobType.Callback,
                )
            )

        super().run()

    @callback
    def _async_update_current_humidity_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state change event listener callback."""
        self._async_update_current_humidity(event.data["new_state"])

    @callback
    def _async_update_current_humidity(self, new_state: State | None) -> None:
        """Handle linked humidity sensor state change to update HomeKit value."""
        if new_state is None or new_state.state in IGNORED_STATES:
            return

        if (
            (current_humidity := convert_to_float(new_state.state)) is None
            or not self.char_current_humidity
            or self.char_current_humidity.value == current_humidity
        ):
            return

        _LOGGER.debug(
            "%s: Linked humidity sensor %s changed to %d",
            self.entity_id,
            self.linked_humidity_sensor,
            current_humidity,
        )
        self.char_current_humidity.set_value(current_humidity)

    @callback
    def _async_update_current_pm25_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state change event listener callback."""
        self._async_update_current_pm25(event.data["new_state"])

    @callback
    def _async_update_current_pm25(self, new_state: State | None) -> None:
        """Handle linked pm25 sensor state change to update HomeKit value."""
        if new_state is None or new_state.state in IGNORED_STATES:
            return

        if (
            (current_pm25 := convert_to_float(new_state.state)) is None
            or not self.char_pm25_density
            or self.char_pm25_density.value == current_pm25
        ):
            return

        _LOGGER.debug(
            "%s: Linked pm25 sensor %s changed to %d",
            self.entity_id,
            self.linked_pm25_sensor,
            current_pm25,
        )
        self.char_pm25_density.set_value(current_pm25)
        air_quality = density_to_air_quality(current_pm25)
        self.char_air_quality.set_value(air_quality)
        _LOGGER.debug("%s: Set air_quality to %d", self.entity_id, air_quality)

    @callback
    def _async_update_current_temperature_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state change event listener callback."""
        self._async_update_current_temperature(event.data["new_state"])

    @callback
    def _async_update_current_temperature(self, new_state: State | None) -> None:
        """Handle linked temperature sensor state change to update HomeKit value."""
        if new_state is None or new_state.state in IGNORED_STATES:
            return

        if (
            (current_temperature := convert_to_float(new_state.state)) is None
            or not self.char_current_temperature
            or self.char_current_temperature.value == current_temperature
        ):
            return

        _LOGGER.debug(
            "%s: Linked temperature sensor %s changed to %d",
            self.entity_id,
            self.linked_temperature_sensor,
            current_temperature,
        )
        self.char_current_temperature.set_value(current_temperature)

    @callback
    def _async_update_filter_change_indicator_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state change event listener callback."""
        self._async_update_filter_change_indicator(event.data.get("new_state"))

    @callback
    def _async_update_filter_change_indicator(self, new_state: State | None) -> None:
        """Handle linked filter change indicator binary sensor state change to update HomeKit value."""
        if new_state is None or new_state.state in IGNORED_STATES:
            return

        current_change_indicator = (
            FILTER_CHANGE_FILTER if new_state.state == "on" else FILTER_OK
        )
        if (
            not self.char_filter_change_indication
            or self.char_filter_change_indication.value == current_change_indicator
        ):
            return

        _LOGGER.debug(
            "%s: Linked filter change indicator binary sensor %s changed to %d",
            self.entity_id,
            self.linked_filter_change_indicator_binary_sensor,
            current_change_indicator,
        )
        self.char_filter_change_indication.set_value(current_change_indicator)

    @callback
    def _async_update_filter_life_level_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state change event listener callback."""
        self._async_update_filter_life_level(event.data.get("new_state"))

    @callback
    def _async_update_filter_life_level(self, new_state: State | None) -> None:
        """Handle linked filter life level sensor state change to update HomeKit value."""
        if new_state is None or new_state.state in IGNORED_STATES:
            return

        if (
            (current_life_level := convert_to_float(new_state.state)) is not None
            and self.char_filter_life_level
            and self.char_filter_life_level.value != current_life_level
        ):
            _LOGGER.debug(
                "%s: Linked filter life level sensor %s changed to %d",
                self.entity_id,
                self.linked_filter_life_level_sensor,
                current_life_level,
            )
            self.char_filter_life_level.set_value(current_life_level)

        if self.linked_filter_change_indicator_binary_sensor or not current_life_level:
            # Handled by its own event listener
            return

        current_change_indicator = (
            FILTER_CHANGE_FILTER
            if (current_life_level < THRESHOLD_FILTER_CHANGE_NEEDED)
            else FILTER_OK
        )
        if (
            not self.char_filter_change_indication
            or self.char_filter_change_indication.value == current_change_indicator
        ):
            return

        _LOGGER.debug(
            "%s: Linked filter life level sensor %s changed to %d",
            self.entity_id,
            self.linked_filter_life_level_sensor,
            current_change_indicator,
        )
        self.char_filter_change_indication.set_value(current_change_indicator)

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update fan after state change."""
        super().async_update_state(new_state)
        # Handle State
        state = new_state.state

        if self.char_current_air_purifier_state is not None:
            self.char_current_air_purifier_state.set_value(
                CURRENT_STATE_PURIFYING_AIR
                if state == STATE_ON
                else CURRENT_STATE_INACTIVE
            )

        # Automatic mode is represented in HASS by a preset called Auto or auto
        attributes = new_state.attributes
        if ATTR_PRESET_MODE in attributes:
            current_preset_mode = attributes.get(ATTR_PRESET_MODE)
            self.char_target_air_purifier_state.set_value(
                TARGET_STATE_AUTO
                if current_preset_mode and current_preset_mode.lower() == "auto"
                else TARGET_STATE_MANUAL
            )

    def set_chars(self, char_values: dict[str, Any]) -> None:
        """Handle automatic mode after state change."""
        super().set_chars(char_values)
        if (
            CHAR_TARGET_AIR_PURIFIER_STATE in char_values
            and self.auto_preset is not None
        ):
            if char_values[CHAR_TARGET_AIR_PURIFIER_STATE] == TARGET_STATE_AUTO:
                super().set_preset_mode(True, self.auto_preset)
            elif self.char_speed is not None:
                super().set_chars({CHAR_ROTATION_SPEED: self.char_speed.get_value()})
