"""Class to hold all thermostat accessories."""

import logging
from typing import Any

from pyhap.const import CATEGORY_HUMIDIFIER
from pyhap.util import callback as pyhap_callback

from homeassistant.components.humidifier import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DOMAIN,
    SERVICE_SET_HUMIDITY,
    HumidifierDeviceClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import Event, State, callback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_ACTIVE,
    CHAR_CURRENT_HUMIDIFIER_DEHUMIDIFIER,
    CHAR_CURRENT_HUMIDITY,
    CHAR_DEHUMIDIFIER_THRESHOLD_HUMIDITY,
    CHAR_HUMIDIFIER_THRESHOLD_HUMIDITY,
    CHAR_TARGET_HUMIDIFIER_DEHUMIDIFIER,
    CONF_LINKED_HUMIDITY_SENSOR,
    PROP_MAX_VALUE,
    PROP_MIN_STEP,
    PROP_MIN_VALUE,
    SERV_HUMIDIFIER_DEHUMIDIFIER,
)

_LOGGER = logging.getLogger(__name__)

HC_HUMIDIFIER = 1
HC_DEHUMIDIFIER = 2

HC_HASS_TO_HOMEKIT_DEVICE_CLASS = {
    HumidifierDeviceClass.HUMIDIFIER: HC_HUMIDIFIER,
    HumidifierDeviceClass.DEHUMIDIFIER: HC_DEHUMIDIFIER,
}

HC_HASS_TO_HOMEKIT_DEVICE_CLASS_NAME = {
    HumidifierDeviceClass.HUMIDIFIER: "Humidifier",
    HumidifierDeviceClass.DEHUMIDIFIER: "Dehumidifier",
}

HC_DEVICE_CLASS_TO_TARGET_CHAR = {
    HC_HUMIDIFIER: CHAR_HUMIDIFIER_THRESHOLD_HUMIDITY,
    HC_DEHUMIDIFIER: CHAR_DEHUMIDIFIER_THRESHOLD_HUMIDITY,
}


HC_STATE_INACTIVE = 0
HC_STATE_IDLE = 1
HC_STATE_HUMIDIFYING = 2
HC_STATE_DEHUMIDIFYING = 3

BASE_VALID_VALUES = {
    "Inactive": HC_STATE_INACTIVE,
    "Idle": HC_STATE_IDLE,
}

VALID_VALUES_BY_DEVICE_CLASS = {
    HumidifierDeviceClass.HUMIDIFIER: {
        **BASE_VALID_VALUES,
        "Humidifying": HC_STATE_HUMIDIFYING,
    },
    HumidifierDeviceClass.DEHUMIDIFIER: {
        **BASE_VALID_VALUES,
        "Dehumidifying": HC_STATE_DEHUMIDIFYING,
    },
}


@TYPES.register("HumidifierDehumidifier")
class HumidifierDehumidifier(HomeAccessory):
    """Generate a HumidifierDehumidifier accessory for a humidifier."""

    def __init__(self, *args: Any) -> None:
        """Initialize a HumidifierDehumidifier accessory object."""
        super().__init__(*args, category=CATEGORY_HUMIDIFIER)
        self._reload_on_change_attrs.extend(
            (
                ATTR_MAX_HUMIDITY,
                ATTR_MIN_HUMIDITY,
            )
        )

        self.chars: list[str] = []
        states = self.hass.states
        state = states.get(self.entity_id)
        assert state
        device_class = state.attributes.get(
            ATTR_DEVICE_CLASS, HumidifierDeviceClass.HUMIDIFIER
        )
        self._hk_device_class = HC_HASS_TO_HOMEKIT_DEVICE_CLASS[device_class]

        self._target_humidity_char_name = HC_DEVICE_CLASS_TO_TARGET_CHAR[
            self._hk_device_class
        ]
        self.chars.append(self._target_humidity_char_name)

        serv_humidifier_dehumidifier = self.add_preload_service(
            SERV_HUMIDIFIER_DEHUMIDIFIER, self.chars
        )

        # Current and target mode characteristics
        self.char_current_humidifier_dehumidifier = (
            serv_humidifier_dehumidifier.configure_char(
                CHAR_CURRENT_HUMIDIFIER_DEHUMIDIFIER,
                value=0,
                valid_values=VALID_VALUES_BY_DEVICE_CLASS[device_class],
            )
        )
        self.char_target_humidifier_dehumidifier = (
            serv_humidifier_dehumidifier.configure_char(
                CHAR_TARGET_HUMIDIFIER_DEHUMIDIFIER,
                value=self._hk_device_class,
                properties={
                    PROP_MIN_VALUE: self._hk_device_class,
                    PROP_MAX_VALUE: self._hk_device_class,
                },
                valid_values={
                    HC_HASS_TO_HOMEKIT_DEVICE_CLASS_NAME[
                        device_class
                    ]: self._hk_device_class
                },
            )
        )

        # Current and target humidity characteristics
        self.char_current_humidity = serv_humidifier_dehumidifier.configure_char(
            CHAR_CURRENT_HUMIDITY, value=0
        )

        self.char_target_humidity = serv_humidifier_dehumidifier.configure_char(
            self._target_humidity_char_name,
            value=45,
            properties={
                PROP_MIN_VALUE: DEFAULT_MIN_HUMIDITY,
                PROP_MAX_VALUE: DEFAULT_MAX_HUMIDITY,
                PROP_MIN_STEP: 1,
            },
        )

        # Active/inactive characteristics
        self.char_active = serv_humidifier_dehumidifier.configure_char(
            CHAR_ACTIVE, value=False
        )

        self.async_update_state(state)

        serv_humidifier_dehumidifier.setter_callback = self._set_chars

        self.linked_humidity_sensor = self.config.get(CONF_LINKED_HUMIDITY_SENSOR)
        if self.linked_humidity_sensor:
            if humidity_state := states.get(self.linked_humidity_sensor):
                self._async_update_current_humidity(humidity_state)

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
                    self.async_update_current_humidity_event,
                )
            )

        super().run()

    @callback
    def async_update_current_humidity_event(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state change event listener callback."""
        self._async_update_current_humidity(event.data["new_state"])

    @callback
    def _async_update_current_humidity(self, new_state: State | None) -> None:
        """Handle linked humidity sensor state change to update HomeKit value."""
        if new_state is None:
            _LOGGER.error(
                (
                    "%s: Unable to update from linked humidity sensor %s: the entity"
                    " state is None"
                ),
                self.entity_id,
                self.linked_humidity_sensor,
            )
            return
        try:
            current_humidity = float(new_state.state)
        except ValueError as ex:
            _LOGGER.debug(
                "%s: Unable to update from linked humidity sensor %s: %s",
                self.entity_id,
                self.linked_humidity_sensor,
                ex,
            )
            return
        self._async_update_current_humidity_value(current_humidity)

    @callback
    def _async_update_current_humidity_value(self, current_humidity: float) -> None:
        """Handle linked humidity or built-in humidity."""
        if self.char_current_humidity.value != current_humidity:
            _LOGGER.debug(
                "%s: Linked humidity sensor %s changed to %d",
                self.entity_id,
                self.linked_humidity_sensor,
                current_humidity,
            )
            self.char_current_humidity.set_value(current_humidity)

    def _set_chars(self, char_values: dict[str, Any]) -> None:
        """Set characteristics based on the data coming from HomeKit."""
        _LOGGER.debug("HumidifierDehumidifier _set_chars: %s", char_values)

        if CHAR_TARGET_HUMIDIFIER_DEHUMIDIFIER in char_values:
            hk_value = char_values[CHAR_TARGET_HUMIDIFIER_DEHUMIDIFIER]
            if self._hk_device_class != hk_value:
                _LOGGER.error(
                    "%s is not supported", CHAR_TARGET_HUMIDIFIER_DEHUMIDIFIER
                )

        if CHAR_ACTIVE in char_values:
            self.async_call_service(
                DOMAIN,
                SERVICE_TURN_ON if char_values[CHAR_ACTIVE] else SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: self.entity_id},
                f"{CHAR_ACTIVE} to {char_values[CHAR_ACTIVE]}",
            )

        if self._target_humidity_char_name in char_values:
            state = self.hass.states.get(self.entity_id)
            assert state
            min_humidity, max_humidity = self.get_humidity_range(state)
            humidity = round(char_values[self._target_humidity_char_name])

            if (humidity < min_humidity) or (humidity > max_humidity):
                humidity = min(max_humidity, max(min_humidity, humidity))
                # Update the HomeKit value to the clamped humidity, so the user will get a visual feedback that they
                # cannot not set to a value below/above the min/max.
                self.char_target_humidity.set_value(humidity)

            self.async_call_service(
                DOMAIN,
                SERVICE_SET_HUMIDITY,
                {ATTR_ENTITY_ID: self.entity_id, ATTR_HUMIDITY: humidity},
                (
                    f"{self._target_humidity_char_name} to "
                    f"{char_values[self._target_humidity_char_name]}{PERCENTAGE}"
                ),
            )

    def get_humidity_range(self, state: State) -> tuple[int, int]:
        """Return min and max humidity range."""
        attributes = state.attributes
        min_humidity = max(
            int(round(attributes.get(ATTR_MIN_HUMIDITY, DEFAULT_MIN_HUMIDITY))), 0
        )
        max_humidity = min(
            int(round(attributes.get(ATTR_MAX_HUMIDITY, DEFAULT_MAX_HUMIDITY))), 100
        )
        return min_humidity, max_humidity

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update state without rechecking the device features."""
        is_active = new_state.state == STATE_ON
        attributes = new_state.attributes

        # Update active state
        self.char_active.set_value(is_active)

        # Set current state
        if is_active:
            if self._hk_device_class == HC_HUMIDIFIER:
                current_state = HC_STATE_HUMIDIFYING
            else:
                current_state = HC_STATE_DEHUMIDIFYING
        else:
            current_state = HC_STATE_INACTIVE
        self.char_current_humidifier_dehumidifier.set_value(current_state)

        # Update target humidity
        target_humidity = attributes.get(ATTR_HUMIDITY)
        if isinstance(target_humidity, (int, float)):
            self.char_target_humidity.set_value(target_humidity)
        current_humidity = attributes.get(ATTR_CURRENT_HUMIDITY)
        if isinstance(current_humidity, (int, float)):
            self.char_current_humidity.set_value(current_humidity)
