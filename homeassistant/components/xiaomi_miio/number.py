"""Support for Xiaomi Mi Air Purifier and Xiaomi Mi Air Humidifier."""
from dataclasses import dataclass
from enum import Enum
import logging

from homeassistant.components.number import NumberEntity
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import callback

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_MODEL,
    DOMAIN,
    FEATURE_FLAGS_AIRHUMIDIFIER,
    FEATURE_FLAGS_AIRHUMIDIFIER_CA4,
    FEATURE_FLAGS_AIRHUMIDIFIER_CA_AND_CB,
    FEATURE_SET_MOTOR_SPEED,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODEL_AIRHUMIDIFIER_CA1,
    MODEL_AIRHUMIDIFIER_CA4,
    MODEL_AIRHUMIDIFIER_CB1,
    MODELS_HUMIDIFIER,
    SERVICE_SET_MOTOR_SPEED,
)
from .device import XiaomiCoordinatedMiioEntity

_LOGGER = logging.getLogger(__name__)

ATTR_MOTOR_SPEED = "motor_speed"
ATTR_ACTUAL_MOTOR_SPEED = "actual_speed"

SERVICE_TO_METHOD = {
    SERVICE_SET_MOTOR_SPEED: {
        "method": "async_set_motor_speed",
        "property": ATTR_MOTOR_SPEED,
    },
}


@dataclass
class NumberType:
    """Class that holds device specific info for a xiaomi aqara or humidifier number controller types."""

    name: str = None
    short_name: str = None
    unit_of_measurement: str = None
    icon: str = None
    device_class: str = None
    min: float = None
    max: float = None
    step: float = None
    service: str = None


NUMBER_TYPES = {
    FEATURE_SET_MOTOR_SPEED: NumberType(
        name="Motor speed",
        icon="mdi:fast-forward-outline",
        short_name=ATTR_MOTOR_SPEED,
        unit_of_measurement="rpm",
        min=200,
        max=2000,
        step=10,
        service=SERVICE_SET_MOTOR_SPEED,
    ),
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Selectors from a config entry."""
    entities = []
    if config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        host = config_entry.data[CONF_HOST]
        token = config_entry.data[CONF_TOKEN]
        model = config_entry.data[CONF_MODEL]
        device = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
        coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]
        device_features = 0
        entity_class = None

        _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])
        if model in [MODEL_AIRHUMIDIFIER_CA1, MODEL_AIRHUMIDIFIER_CB1]:
            device_features = FEATURE_FLAGS_AIRHUMIDIFIER_CA_AND_CB
            entity_class = XiaomiAirHumidifierNumber
        elif model in [MODEL_AIRHUMIDIFIER_CA4]:
            device_features = FEATURE_FLAGS_AIRHUMIDIFIER_CA4
            entity_class = XiaomiAirHumidifierNumber
        elif model in MODELS_HUMIDIFIER:
            device_features = FEATURE_FLAGS_AIRHUMIDIFIER
            entity_class = XiaomiAirHumidifierNumber
        else:
            return

        for feature in NUMBER_TYPES:
            number = NUMBER_TYPES[feature]
            if feature & device_features and feature in NUMBER_TYPES:
                entities.append(
                    entity_class(
                        f"{config_entry.title} {number.name}",
                        device,
                        config_entry,
                        f"{number.short_name}_{config_entry.unique_id}",
                        number,
                        coordinator,
                    )
                )

    async_add_entities(entities, update_before_add=True)


class XiaomiNumber(XiaomiCoordinatedMiioEntity, NumberEntity):
    """Representation of a generic Xiaomi attribute selector."""

    def __init__(self, name, device, entry, unique_id, number, coordinator):
        """Initialize the generic Xiaomi attribute selector."""
        super().__init__(name, device, entry, unique_id, coordinator)
        self._state = None
        self._attr_icon = number.icon
        self._attr_unit_of_measurement = number.unit_of_measurement
        self._attr_min_value = number.min
        self._attr_max_value = number.max
        self._attr_step = number.step
        self._supported_features = 0
        self._device_features = 0
        self._state_attrs = {}
        self._controller = number
        self._enum_class = None
        self._attributes = None
        self._value = None

    @property
    def available(self):
        """Return true when state is known."""
        return super().available and self._available

    @property
    def value(self):
        """Return the current option."""
        return self._value if self.available else None

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value

        return value

    async def async_set_value(self, value):
        """Set an option of the miio device."""
        if not self.available:
            return
        if (
            self.min_value
            and value < self.min_value
            or self.max_value
            and value > self.max_value
        ):
            _LOGGER.warning(
                "Value %s not a valid %s within the range %s - %s",
                value,
                self.name,
                self.min_value,
                self.max_value,
            )
            return
        method = getattr(self, SERVICE_TO_METHOD[self._controller.service]["method"])
        await method(value)


class XiaomiAirHumidifierNumber(XiaomiNumber):
    """Representation of a Xiaomi Air Humidifier selector."""

    def __init__(self, name, device, entry, unique_id, controller, coordinator):
        """Initialize the plug switch."""
        super().__init__(name, device, entry, unique_id, controller, coordinator)
        if self._model in [MODEL_AIRHUMIDIFIER_CA1, MODEL_AIRHUMIDIFIER_CB1]:
            self._device_features = FEATURE_FLAGS_AIRHUMIDIFIER_CA_AND_CB
        elif self._model in [MODEL_AIRHUMIDIFIER_CA4]:
            self._device_features = FEATURE_FLAGS_AIRHUMIDIFIER_CA4
        else:
            self._device_features = FEATURE_FLAGS_AIRHUMIDIFIER

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        state = self.coordinator.data
        if not state:
            return
        _LOGGER.debug("Got new state: %s", state)
        self._available = True
        self._value = self._extract_value_from_attribute(
            state, self._controller.short_name
        )
        self.async_write_ha_state()

    async def async_set_motor_speed(self, motor_speed: int = 400):
        """Set the target motor speed."""
        if self._device_features & FEATURE_SET_MOTOR_SPEED == 0:
            return

        await self._try_command(
            "Setting the target motor speed of the miio device failed.",
            self._device.set_speed,
            motor_speed,
        )
