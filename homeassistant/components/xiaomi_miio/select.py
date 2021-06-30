"""Support led_brightness for Mi Air Humidifier."""
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


LED_BRIGHTNESS_MAP = {"Bright": 0, "Dim": 1, "Off": 2}
LED_BRIGHTNESS_MAP_MIOT = {"Bright": 2, "Dim": 1, "Off": 0}
LED_BRIGHTNESS_REVERSE_MAP = {val: key for key, val in LED_BRIGHTNESS_MAP.items()}
LED_BRIGHTNESS_REVERSE_MAP_MIOT = {
    val: key for key, val in LED_BRIGHTNESS_MAP_MIOT.items()
}


@dataclass
class SelectorType:
    """Class that holds device specific info for a xiaomi aqara or humidifier selectors."""

    name: str = None
    icon: str = None
    short_name: str = None
    options: list = None
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
    if not config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        return

    entities = []
    host = config_entry.data[CONF_HOST]
    token = config_entry.data[CONF_TOKEN]
    model = config_entry.data[CONF_MODEL]
    device = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

    if model in [MODEL_AIRHUMIDIFIER_CA1, MODEL_AIRHUMIDIFIER_CB1]:
        entity_class = XiaomiAirHumidifierSelector
    elif model in [MODEL_AIRHUMIDIFIER_CA4]:
        entity_class = XiaomiAirHumidifierMiotSelector
    elif model in MODELS_HUMIDIFIER:
        entity_class = XiaomiAirHumidifierSelector
    else:
        return

    for feature in SELECTOR_TYPES:
        selector = SELECTOR_TYPES[feature]
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
        self._controller = selector
        self._attr_options = self._controller.options

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value

        return value


class XiaomiAirHumidifierSelector(XiaomiSelector):
    """Representation of a Xiaomi Air Humidifier selector."""

    def __init__(self, name, device, entry, unique_id, controller, coordinator):
        """Initialize the plug switch."""
        super().__init__(name, device, entry, unique_id, controller, coordinator)
        self._current_led_brightness = self._extract_value_from_attribute(
            self.coordinator.data, self._controller.short_name
        )

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._current_led_brightness = self._extract_value_from_attribute(
            self.coordinator.data, self._controller.short_name
        )
        self.async_write_ha_state()

    @property
    def current_option(self):
        """Return the current option."""
        return self.led_brightness

    async def async_select_option(self, option: str) -> None:
        """Set an option of the miio device."""
        if option not in self.options:
            raise ValueError(
                f"Selection '{option}' is not a valid {self._controller.name}"
            )
        await self.async_set_led_brightness(option)

    @property
    def led_brightness(self):
        """Return the current led brightness."""
        return LED_BRIGHTNESS_REVERSE_MAP.get(self._current_led_brightness)

    async def async_set_led_brightness(self, brightness: str):
        """Set the led brightness."""
        if await self._try_command(
            "Setting the led brightness of the miio device failed.",
            self._device.set_led_brightness,
            AirhumidifierLedBrightness(LED_BRIGHTNESS_MAP[brightness]),
        ):
            self._current_led_brightness = LED_BRIGHTNESS_MAP[brightness]
            self.async_write_ha_state()


class XiaomiAirHumidifierMiotSelector(XiaomiAirHumidifierSelector):
    """Representation of a Xiaomi Air Humidifier (MiOT protocol) selector."""

    @property
    def led_brightness(self):
        """Return the current led brightness."""
        return LED_BRIGHTNESS_REVERSE_MAP_MIOT.get(self._current_led_brightness)

    async def async_set_led_brightness(self, brightness: str):
        """Set the led brightness."""
        if await self._try_command(
            "Setting the led brightness of the miio device failed.",
            self._device.set_led_brightness,
            AirhumidifierMiotLedBrightness(LED_BRIGHTNESS_MAP_MIOT[brightness]),
        ):
            self._current_led_brightness = LED_BRIGHTNESS_MAP_MIOT[brightness]
            self.async_write_ha_state()
