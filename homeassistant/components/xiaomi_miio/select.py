"""Support led_brightness for Mi Air Humidifier."""
from __future__ import annotations

from dataclasses import dataclass, field

from miio.airfresh import LedBrightness as AirfreshLedBrightness
from miio.airfresh_t2017 import (
    DisplayOrientation as AirfreshT2017DisplayOrientation,
    PtcLevel as AirfreshT2017PtcLevel,
)
from miio.airhumidifier import LedBrightness as AirhumidifierLedBrightness
from miio.airhumidifier_miot import LedBrightness as AirhumidifierMiotLedBrightness
from miio.airpurifier import LedBrightness as AirpurifierLedBrightness
from miio.airpurifier_miot import LedBrightness as AirpurifierMiotLedBrightness
from miio.fan_common import LedBrightness as FanLedBrightness

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_MODEL,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODEL_AIRFRESH_T2017,
    MODEL_AIRFRESH_VA2,
    MODEL_AIRHUMIDIFIER_CA1,
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

ATTR_DISPLAY_ORIENTATION = "display_orientation"
ATTR_LED_BRIGHTNESS = "led_brightness"
ATTR_PTC_LEVEL = "ptc_level"


LED_BRIGHTNESS_MAP = {"Bright": 0, "Dim": 1, "Off": 2}
LED_BRIGHTNESS_MAP_HUMIDIFIER_MIOT = {"Bright": 2, "Dim": 1, "Off": 0}
LED_BRIGHTNESS_REVERSE_MAP = {val: key for key, val in LED_BRIGHTNESS_MAP.items()}
LED_BRIGHTNESS_REVERSE_MAP_HUMIDIFIER_MIOT = {
    val: key for key, val in LED_BRIGHTNESS_MAP_HUMIDIFIER_MIOT.items()
}
PTC_LEVEL_MAP = {"Low": "low", "Medium": "medium", "High": "high"}
PTC_LEVEL_REVERSE_MAP = {val: key for key, val in PTC_LEVEL_MAP.items()}
DISPLAY_ORIENTATION_MAP = {"Forward": "forward", "Left": "left", "Right": "right"}
DISPLAY_ORIENTATION_REVERSE_MAP = {
    val: key for key, val in DISPLAY_ORIENTATION_MAP.items()
}


@dataclass
class XiaomiMiioSelectDescription(SelectEntityDescription):
    """A class that describes select entities."""

    options_map: dict = field(default_factory=dict)
    reverse_map: dict = field(default_factory=dict)
    set_method: str = ""
    set_method_error_message: str = ""
    options: tuple = ()


MODEL_TO_ATTR_MAP = {
    MODEL_AIRFRESH_T2017: [
        (ATTR_DISPLAY_ORIENTATION, AirfreshT2017DisplayOrientation),
        (ATTR_PTC_LEVEL, AirfreshT2017PtcLevel),
    ],
    MODEL_AIRHUMIDIFIER_CA1: [(ATTR_LED_BRIGHTNESS, AirhumidifierLedBrightness)],
}

SELECTOR_TYPES = (
    XiaomiMiioSelectDescription(
        key=ATTR_DISPLAY_ORIENTATION,
        name="Display Orientation",
        options_map=DISPLAY_ORIENTATION_MAP,
        reverse_map=DISPLAY_ORIENTATION_REVERSE_MAP,
        set_method="set_display_orientation",
        set_method_error_message="Setting the display orientation failed.",
        icon="mdi:tablet",
        device_class="xiaomi_miio__display_orientation",
        options=("forward", "left", "right"),
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioSelectDescription(
        key=ATTR_LED_BRIGHTNESS,
        name="Led Brightness",
        options_map=LED_BRIGHTNESS_MAP,
        reverse_map=LED_BRIGHTNESS_REVERSE_MAP,
        set_method="set_led_brightness",
        set_method_error_message="Setting the led brightness failed.",
        icon="mdi:brightness-6",
        device_class="xiaomi_miio__led_brightness",
        options=("bright", "dim", "off"),
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioSelectDescription(
        key=ATTR_PTC_LEVEL,
        name="Auxiliary Heat Level",
        options_map=PTC_LEVEL_MAP,
        reverse_map=PTC_LEVEL_REVERSE_MAP,
        set_method="set_ptc_level",
        set_method_error_message="Setting the ptc level failed.",
        icon="mdi:fire-circle",
        device_class="xiaomi_miio__ptc_level",
        options=("low", "medium", "high"),
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Selectors from a config entry."""
    if not config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        return

    model = config_entry.data[CONF_MODEL]
    if model in MODEL_TO_ATTR_MAP:
        await async_setup_generic_entry(hass, config_entry, async_add_entities)
    else:
        await async_setup_other_entry(hass, config_entry, async_add_entities)


async def async_setup_generic_entry(hass, config_entry, async_add_entities):
    """Set up the generic Selectors from a config entry."""
    entities = []
    unique_id = config_entry.unique_id
    device = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]
    model = config_entry.data[CONF_MODEL]
    attributes = MODEL_TO_ATTR_MAP[model]

    for description in SELECTOR_TYPES:
        for attribute in attributes:
            if description.key == attribute[0]:
                entities.append(
                    XiaomiGenericSelector(
                        f"{config_entry.title} {description.name}",
                        device,
                        config_entry,
                        f"{description.key}_{unique_id}",
                        coordinator,
                        description,
                        attribute[1],
                    )
                )

    async_add_entities(entities)


async def async_setup_other_entry(hass, config_entry, async_add_entities):
    """Set up the other type Selectors from a config entry."""
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

    for description in SELECTOR_TYPES:
        if description.key == ATTR_LED_BRIGHTNESS:
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


class XiaomiGenericSelector(XiaomiSelector):
    """Representation of a Xiaomi generic selector."""

    entity_description: XiaomiMiioSelectDescription

    def __init__(
        self, name, device, entry, unique_id, coordinator, description, enum_class
    ):
        """Initialize the generic Xiaomi attribute selector."""
        super().__init__(name, device, entry, unique_id, coordinator, description)
        self._current_attr = self._extract_value_from_attribute(
            self.coordinator.data, self.entity_description.key
        )
        self._enum_class = enum_class

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        attr = self._extract_value_from_attribute(
            self.coordinator.data, self.entity_description.key
        )
        if attr is not None:
            self._current_attr = attr
            self.async_write_ha_state()

    @property
    def current_option(self):
        """Return the current option."""
        return self.attr.lower()

    async def async_select_option(self, option: str) -> None:
        """Set an option of the miio device."""
        await self.async_set_attr(option.title())

    @property
    def attr(self):
        """Return the current ptc level."""
        return self.entity_description.reverse_map.get(self._current_attr)

    async def async_set_attr(self, attr_value: str):
        """Set attr."""
        method = getattr(self._device, self.entity_description.set_method)
        if await self._try_command(
            self.entity_description.set_method_error_message,
            method,
            self._enum_class(self.entity_description.options_map[attr_value]),
        ):
            self._current_attr = self.entity_description.options_map[attr_value]
            self.async_write_ha_state()


class XiaomiAirHumidifierSelector(XiaomiSelector):
    """Representation of a Xiaomi Air Humidifier selector."""

    def __init__(self, name, device, entry, unique_id, coordinator, description):
        """Initialize the Xiaomi Air Humidifier selector."""
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
        if led_brightness is not None:
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
