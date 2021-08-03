"""Support led_brightness for Mi Air Humidifier."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from miio.airhumidifier import LedBrightness as AirhumidifierLedBrightness
from miio.airhumidifier_miot import LedBrightness as AirhumidifierMiotLedBrightness

from homeassistant.components.select import SelectEntity, SelectEntityDescription
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
)
from .device import XiaomiCoordinatedMiioEntity

ATTR_LED_BRIGHTNESS = "led_brightness"


LED_BRIGHTNESS_MAP = {"Bright": 0, "Dim": 1, "Off": 2}
LED_BRIGHTNESS_MAP_MIOT = {"Bright": 2, "Dim": 1, "Off": 0}
LED_BRIGHTNESS_REVERSE_MAP = {val: key for key, val in LED_BRIGHTNESS_MAP.items()}
LED_BRIGHTNESS_REVERSE_MAP_MIOT = {
    val: key for key, val in LED_BRIGHTNESS_MAP_MIOT.items()
}


@dataclass
class XiaomiMiioSelectDescription(SelectEntityDescription):
    """A class that describes select entities."""

    options: tuple = ()


SELECTOR_TYPES = {
    FEATURE_SET_LED_BRIGHTNESS: XiaomiMiioSelectDescription(
        key=ATTR_LED_BRIGHTNESS,
        name="Led Brightness",
        icon="mdi:brightness-6",
        device_class="xiaomi_miio__led_brightness",
        options=("bright", "dim", "off"),
    ),
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Selectors from a config entry."""
    if not config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        return

    entities = []
    model = config_entry.data[CONF_MODEL]
    device = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]

    if model in [MODEL_AIRHUMIDIFIER_CA1, MODEL_AIRHUMIDIFIER_CB1]:
        entity_class = XiaomiAirHumidifierSelector
    elif model in [MODEL_AIRHUMIDIFIER_CA4]:
        entity_class = XiaomiAirHumidifierMiotSelector
    elif model in MODELS_HUMIDIFIER:
        entity_class = XiaomiAirHumidifierSelector
    else:
        return

    description = SELECTOR_TYPES[FEATURE_SET_LED_BRIGHTNESS]
    entities.append(
        entity_class(
            f"{config_entry.title} {description.name}",
            device,
            config_entry,
            f"{description.key}_{config_entry.unique_id}",
            hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR],
            description,
        )
    )

    async_add_entities(entities)


class XiaomiSelector(XiaomiCoordinatedMiioEntity, SelectEntity):
    """Representation of a generic Xiaomi attribute selector."""

    def __init__(self, name, device, entry, unique_id, coordinator, description):
        """Initialize the generic Xiaomi attribute selector."""
        super().__init__(name, device, entry, unique_id, coordinator)
        self._attr_options = list(description.options)
        self.entity_description = description

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value

        return value


class XiaomiAirHumidifierSelector(XiaomiSelector):
    """Representation of a Xiaomi Air Humidifier selector."""

    def __init__(self, name, device, entry, unique_id, coordinator, description):
        """Initialize the plug switch."""
        super().__init__(name, device, entry, unique_id, coordinator, description)
        self._current_led_brightness = self._extract_value_from_attribute(
            self.coordinator.data, self.entity_description.key
        )

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._current_led_brightness = self._extract_value_from_attribute(
            self.coordinator.data, self.entity_description.key
        )
        self.async_write_ha_state()

    @property
    def current_option(self):
        """Return the current option."""
        return self.led_brightness.lower()

    async def async_select_option(self, option: str) -> None:
        """Set an option of the miio device."""
        if option not in self.options:
            raise ValueError(
                f"Selection '{option}' is not a valid {self.entity_description.name}"
            )
        await self.async_set_led_brightness(option.title())

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
