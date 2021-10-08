"""Support led_brightness for Mi Air Humidifier."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from miio.airfresh import LedBrightness as AirfreshLedBrightness
from miio.airhumidifier import LedBrightness as AirhumidifierLedBrightness
from miio.airhumidifier_miot import LedBrightness as AirhumidifierMiotLedBrightness
from miio.airpurifier import LedBrightness as AirpurifierLedBrightness
from miio.airpurifier_miot import LedBrightness as AirpurifierMiotLedBrightness
from miio.fan import LedBrightness as FanLedBrightness

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
    MODEL_AIRFRESH_VA2,
    MODEL_AIRPURIFIER_3C,
    MODEL_AIRPURIFIER_M1,
    MODEL_AIRPURIFIER_M2,
    MODEL_FAN_SA1,
    MODEL_FAN_V2,
    MODEL_FAN_V3,
    MODEL_FAN_ZA1,
    MODEL_FAN_ZA3,
    MODEL_FAN_ZA4,
    MODELS_HUMIDIFIER_MIIO,
    MODELS_HUMIDIFIER_MIOT,
    MODELS_PURIFIER_MIOT,
)
from .device import XiaomiCoordinatedMiioEntity

ATTR_LED_BRIGHTNESS = "led_brightness"


LED_BRIGHTNESS_MAP = {"Bright": 0, "Dim": 1, "Off": 2}
LED_BRIGHTNESS_MAP_HUMIDIFIER_MIOT = {"Bright": 2, "Dim": 1, "Off": 0}
LED_BRIGHTNESS_REVERSE_MAP = {val: key for key, val in LED_BRIGHTNESS_MAP.items()}
LED_BRIGHTNESS_REVERSE_MAP_HUMIDIFIER_MIOT = {
    val: key for key, val in LED_BRIGHTNESS_MAP_HUMIDIFIER_MIOT.items()
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

    if model == MODEL_AIRPURIFIER_3C:
        return
    if model in MODELS_HUMIDIFIER_MIIO:
        entity_class = XiaomiAirHumidifierSelector
    elif model in MODELS_HUMIDIFIER_MIOT:
        entity_class = XiaomiAirHumidifierMiotSelector
    elif model in [MODEL_AIRPURIFIER_M1, MODEL_AIRPURIFIER_M2]:
        entity_class = XiaomiAirPurifierSelector
    elif model in MODELS_PURIFIER_MIOT:
        entity_class = XiaomiAirPurifierMiotSelector
    elif model == MODEL_AIRFRESH_VA2:
        entity_class = XiaomiAirFreshSelector
    elif model in (
        MODEL_FAN_ZA1,
        MODEL_FAN_ZA3,
        MODEL_FAN_ZA4,
        MODEL_FAN_SA1,
        MODEL_FAN_V2,
        MODEL_FAN_V3,
    ):
        entity_class = XiaomiFanSelector
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
        led_brightness = self._extract_value_from_attribute(
            self.coordinator.data, self.entity_description.key
        )
        # Sometimes (quite rarely) the device returns None as the LED brightness so we
        # check that the value is not None before updating the state.
        if led_brightness:
            self._current_led_brightness = led_brightness
            self.async_write_ha_state()

    @property
    def current_option(self):
        """Return the current option."""
        return self.led_brightness.lower()

    async def async_select_option(self, option: str) -> None:
        """Set an option of the miio device."""
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
        return LED_BRIGHTNESS_REVERSE_MAP_HUMIDIFIER_MIOT.get(
            self._current_led_brightness
        )

    async def async_set_led_brightness(self, brightness: str) -> None:
        """Set the led brightness."""
        if await self._try_command(
            "Setting the led brightness of the miio device failed.",
            self._device.set_led_brightness,
            AirhumidifierMiotLedBrightness(
                LED_BRIGHTNESS_MAP_HUMIDIFIER_MIOT[brightness]
            ),
        ):
            self._current_led_brightness = LED_BRIGHTNESS_MAP_HUMIDIFIER_MIOT[
                brightness
            ]
            self.async_write_ha_state()


class XiaomiAirPurifierSelector(XiaomiAirHumidifierSelector):
    """Representation of a Xiaomi Air Purifier (MIIO protocol) selector."""

    async def async_set_led_brightness(self, brightness: str) -> None:
        """Set the led brightness."""
        if await self._try_command(
            "Setting the led brightness of the miio device failed.",
            self._device.set_led_brightness,
            AirpurifierLedBrightness(LED_BRIGHTNESS_MAP[brightness]),
        ):
            self._current_led_brightness = LED_BRIGHTNESS_MAP[brightness]
            self.async_write_ha_state()


class XiaomiAirPurifierMiotSelector(XiaomiAirHumidifierSelector):
    """Representation of a Xiaomi Air Purifier (MiOT protocol) selector."""

    async def async_set_led_brightness(self, brightness: str) -> None:
        """Set the led brightness."""
        if await self._try_command(
            "Setting the led brightness of the miio device failed.",
            self._device.set_led_brightness,
            AirpurifierMiotLedBrightness(LED_BRIGHTNESS_MAP[brightness]),
        ):
            self._current_led_brightness = LED_BRIGHTNESS_MAP[brightness]
            self.async_write_ha_state()


class XiaomiFanSelector(XiaomiAirHumidifierSelector):
    """Representation of a Xiaomi Fan (MIIO protocol) selector."""

    async def async_set_led_brightness(self, brightness: str) -> None:
        """Set the led brightness."""
        if await self._try_command(
            "Setting the led brightness of the miio device failed.",
            self._device.set_led_brightness,
            FanLedBrightness(LED_BRIGHTNESS_MAP[brightness]),
        ):
            self._current_led_brightness = LED_BRIGHTNESS_MAP[brightness]
            self.async_write_ha_state()


class XiaomiAirFreshSelector(XiaomiAirHumidifierSelector):
    """Representation of a Xiaomi Air Fresh selector."""

    async def async_set_led_brightness(self, brightness: str) -> None:
        """Set the led brightness."""
        if await self._try_command(
            "Setting the led brightness of the miio device failed.",
            self._device.set_led_brightness,
            AirfreshLedBrightness(LED_BRIGHTNESS_MAP[brightness]),
        ):
            self._current_led_brightness = LED_BRIGHTNESS_MAP[brightness]
            self.async_write_ha_state()
