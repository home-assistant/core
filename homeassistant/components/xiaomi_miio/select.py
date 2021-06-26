"""Support for Xiaomi Mi Air Purifier and Xiaomi Mi Air Humidifier."""
from dataclasses import dataclass
from enum import Enum
import logging

from miio.airhumidifier import LedBrightness as AirhumidifierLedBrightness
from miio.airhumidifier_miot import LedBrightness as AirhumidifierMiotLedBrightness

from homeassistant.components.select import SelectEntity
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
    FEATURE_SET_LED_BRIGHTNESS,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODEL_AIRHUMIDIFIER_CA1,
    MODEL_AIRHUMIDIFIER_CA4,
    MODEL_AIRHUMIDIFIER_CB1,
    MODELS_HUMIDIFIER,
    SERVICE_SET_LED_BRIGHTNESS,
)
from .device import XiaomiCoordinatedMiioEntity

_LOGGER = logging.getLogger(__name__)

ATTR_LED_BRIGHTNESS = "led_brightness"

SERVICE_TO_METHOD = {
    SERVICE_SET_LED_BRIGHTNESS: {
        "method": "async_set_led_brightness",
        "property": ATTR_LED_BRIGHTNESS,
    },
}


@dataclass
class SelectorType:
    """Class that holds device specific info for a xiaomi aqara or humidifier selectors."""

    name: str = None
    short_name: str = None
    unit_of_measurement: str = None
    icon: str = None
    device_class: str = None
    min: float = None
    max: float = None
    mode: str = None
    options: list = None
    step: float = None
    service: str = None


SELECTOR_TYPES = {
    FEATURE_SET_LED_BRIGHTNESS: SelectorType(
        name="Led brightness",
        icon="mdi:brightness-6",
        short_name=ATTR_LED_BRIGHTNESS,
        options=["Bright", "Dim", "Off"],
        service=SERVICE_SET_LED_BRIGHTNESS,
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
            entity_class = XiaomiAirHumidifierSelector
        elif model in [MODEL_AIRHUMIDIFIER_CA4]:
            device_features = FEATURE_FLAGS_AIRHUMIDIFIER_CA4
            entity_class = XiaomiAirHumidifierMiotSelector
        elif model in MODELS_HUMIDIFIER:
            device_features = FEATURE_FLAGS_AIRHUMIDIFIER
            entity_class = XiaomiAirHumidifierSelector
        else:
            return

        for feature in SELECTOR_TYPES:
            selector = SELECTOR_TYPES[feature]
            if feature & device_features and feature in SELECTOR_TYPES:
                entities.append(
                    entity_class(
                        f"{config_entry.title} {selector.name}",
                        device,
                        config_entry,
                        f"{selector.short_name}_{config_entry.unique_id}",
                        selector,
                        coordinator,
                    )
                )

    async_add_entities(entities)


class XiaomiSelector(XiaomiCoordinatedMiioEntity, SelectEntity):
    """Representation of a generic Xiaomi attribute selector."""

    def __init__(self, name, device, entry, unique_id, selector, coordinator):
        """Initialize the generic Xiaomi attribute selector."""
        super().__init__(name, device, entry, unique_id, coordinator)
        self._attr_icon = selector.icon
        self._attr_unit_of_measurement = selector.unit_of_measurement
        self._supported_features = 0
        self._device_features = 0
        self._state_attrs = {}
        self._controller = selector
        self._current_option = None
        self._enum_class = None
        self._attributes = None
        self._available_attributes = []

    @property
    def options(self):
        """Return available options."""
        return self._controller.options

    @property
    def available(self):
        """Return true when state is known."""
        return super().available and self._available

    @property
    def current_option(self):
        """Return the current option."""
        return getattr(self, SERVICE_TO_METHOD[self._controller.service]["property"])

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value

        return value

    async def async_select_option(self, option: str) -> None:
        """Set an option of the miio device."""
        if option not in self.options:
            _LOGGER.warning(
                "Selection '%s' is not a valid '%s'", option, self._controller.name
            )
            return
        method = getattr(self, SERVICE_TO_METHOD[self._controller.service]["method"])
        await method(option)


class XiaomiAirHumidifierSelector(XiaomiSelector):
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

        self._state_attrs.update(
            {attribute: None for attribute in self._available_attributes}
        )

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._available = True
        self._current_option = self._extract_value_from_attribute(
            self.coordinator.data, self._controller.short_name
        )
        self.async_write_ha_state()

    @property
    def led_brightness(self):
        """Return the current led brightness."""
        reversed_value_map = {0: "Bright", 1: "Dim", 2: "Off"}
        if self._current_option in reversed_value_map:
            return reversed_value_map[self._current_option]
        return None

    async def async_set_led_brightness(self, brightness: str):
        """Set the led brightness."""
        value_map = {"Bright": 0, "Dim": 1, "Off": 2}
        if self._device_features & FEATURE_SET_LED_BRIGHTNESS == 0:
            return

        if await self._try_command(
            "Setting the led brightness of the miio device failed.",
            self._device.set_led_brightness,
            AirhumidifierLedBrightness(value_map[brightness]),
        ):
            self._current_option = value_map[brightness]
            self.async_write_ha_state()


class XiaomiAirHumidifierMiotSelector(XiaomiAirHumidifierSelector):
    """Representation of a Xiaomi Air Humidifier (MiOT protocol) selector."""

    @property
    def led_brightness(self):
        """Return the current led brightness."""
        reversed_value_map = {0: "Off", 1: "Dim", 2: "Bright"}
        if self._current_option in reversed_value_map:
            return reversed_value_map[self._current_option]
        return None

    async def async_set_led_brightness(self, brightness: str):
        """Set the led brightness."""
        value_map = {"Bright": 2, "Dim": 1, "Off": 0}
        if self._device_features & FEATURE_SET_LED_BRIGHTNESS == 0:
            return

        if await self._try_command(
            "Setting the led brightness of the miio device failed.",
            self._device.set_led_brightness,
            AirhumidifierMiotLedBrightness(value_map[brightness]),
        ):
            self._current_option = value_map[brightness]
            self.async_write_ha_state()
