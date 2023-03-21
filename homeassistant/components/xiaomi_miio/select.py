"""Support led_brightness for Mi Air Humidifier."""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import NamedTuple

from miio.fan_common import LedBrightness as FanLedBrightness
from miio.integrations.airpurifier.dmaker.airfresh_t2017 import (
    DisplayOrientation as AirfreshT2017DisplayOrientation,
    PtcLevel as AirfreshT2017PtcLevel,
)
from miio.integrations.airpurifier.zhimi.airfresh import (
    LedBrightness as AirfreshLedBrightness,
)
from miio.integrations.airpurifier.zhimi.airpurifier import (
    LedBrightness as AirpurifierLedBrightness,
    OperationMode as AirpurifierOperationMode,
)
from miio.integrations.airpurifier.zhimi.airpurifier_miot import (
    LedBrightness as AirpurifierMiotLedBrightness,
)
from miio.integrations.humidifier.zhimi.airhumidifier import (
    LedBrightness as AirhumidifierLedBrightness,
)
from miio.integrations.humidifier.zhimi.airhumidifier_miot import (
    LedBrightness as AirhumidifierMiotLedBrightness,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODEL_AIRFRESH_T2017,
    MODEL_AIRFRESH_VA2,
    MODEL_AIRFRESH_VA4,
    MODEL_AIRHUMIDIFIER_CA1,
    MODEL_AIRHUMIDIFIER_CA4,
    MODEL_AIRHUMIDIFIER_CB1,
    MODEL_AIRHUMIDIFIER_V1,
    MODEL_AIRPURIFIER_3,
    MODEL_AIRPURIFIER_3H,
    MODEL_AIRPURIFIER_4,
    MODEL_AIRPURIFIER_4_PRO,
    MODEL_AIRPURIFIER_M1,
    MODEL_AIRPURIFIER_M2,
    MODEL_AIRPURIFIER_MA2,
    MODEL_AIRPURIFIER_PROH,
    MODEL_AIRPURIFIER_ZA1,
    MODEL_FAN_SA1,
    MODEL_FAN_V2,
    MODEL_FAN_V3,
    MODEL_FAN_ZA1,
    MODEL_FAN_ZA3,
    MODEL_FAN_ZA4,
)
from .device import XiaomiCoordinatedMiioEntity

ATTR_DISPLAY_ORIENTATION = "display_orientation"
ATTR_LED_BRIGHTNESS = "led_brightness"
ATTR_PTC_LEVEL = "ptc_level"
ATTR_MODE = "mode"

_LOGGER = logging.getLogger(__name__)


@dataclass
class XiaomiMiioSelectDescription(SelectEntityDescription):
    """A class that describes select entities."""

    attr_name: str = ""
    options_map: dict = field(default_factory=dict)
    set_method: str = ""
    set_method_error_message: str = ""


class AttributeEnumMapping(NamedTuple):
    """Class to mapping Attribute to Enum Class."""

    attr_name: str
    enum_class: type


MODEL_TO_ATTR_MAP: dict[str, list] = {
    MODEL_AIRFRESH_T2017: [
        AttributeEnumMapping(ATTR_DISPLAY_ORIENTATION, AirfreshT2017DisplayOrientation),
        AttributeEnumMapping(ATTR_PTC_LEVEL, AirfreshT2017PtcLevel),
    ],
    MODEL_AIRFRESH_VA2: [
        AttributeEnumMapping(ATTR_LED_BRIGHTNESS, AirfreshLedBrightness)
    ],
    MODEL_AIRFRESH_VA4: [
        AttributeEnumMapping(ATTR_LED_BRIGHTNESS, AirfreshLedBrightness)
    ],
    MODEL_AIRHUMIDIFIER_CA1: [
        AttributeEnumMapping(ATTR_LED_BRIGHTNESS, AirhumidifierLedBrightness)
    ],
    MODEL_AIRHUMIDIFIER_CA4: [
        AttributeEnumMapping(ATTR_LED_BRIGHTNESS, AirhumidifierMiotLedBrightness)
    ],
    MODEL_AIRHUMIDIFIER_CB1: [
        AttributeEnumMapping(ATTR_LED_BRIGHTNESS, AirhumidifierLedBrightness)
    ],
    MODEL_AIRHUMIDIFIER_V1: [
        AttributeEnumMapping(ATTR_LED_BRIGHTNESS, AirhumidifierLedBrightness)
    ],
    MODEL_AIRPURIFIER_MA2: [AttributeEnumMapping(ATTR_MODE, AirpurifierOperationMode)],
    MODEL_AIRPURIFIER_3: [
        AttributeEnumMapping(ATTR_LED_BRIGHTNESS, AirpurifierMiotLedBrightness)
    ],
    MODEL_AIRPURIFIER_ZA1: [
        AttributeEnumMapping(ATTR_LED_BRIGHTNESS, AirpurifierMiotLedBrightness)
    ],
    MODEL_AIRPURIFIER_3H: [
        AttributeEnumMapping(ATTR_LED_BRIGHTNESS, AirpurifierMiotLedBrightness)
    ],
    MODEL_AIRPURIFIER_4: [
        AttributeEnumMapping(ATTR_LED_BRIGHTNESS, AirpurifierMiotLedBrightness)
    ],
    MODEL_AIRPURIFIER_4_PRO: [
        AttributeEnumMapping(ATTR_LED_BRIGHTNESS, AirpurifierMiotLedBrightness)
    ],
    MODEL_AIRPURIFIER_M1: [
        AttributeEnumMapping(ATTR_LED_BRIGHTNESS, AirpurifierLedBrightness)
    ],
    MODEL_AIRPURIFIER_M2: [
        AttributeEnumMapping(ATTR_LED_BRIGHTNESS, AirpurifierLedBrightness)
    ],
    MODEL_AIRPURIFIER_PROH: [
        AttributeEnumMapping(ATTR_LED_BRIGHTNESS, AirpurifierMiotLedBrightness)
    ],
    MODEL_FAN_SA1: [AttributeEnumMapping(ATTR_LED_BRIGHTNESS, FanLedBrightness)],
    MODEL_FAN_V2: [AttributeEnumMapping(ATTR_LED_BRIGHTNESS, FanLedBrightness)],
    MODEL_FAN_V3: [AttributeEnumMapping(ATTR_LED_BRIGHTNESS, FanLedBrightness)],
    MODEL_FAN_ZA1: [AttributeEnumMapping(ATTR_LED_BRIGHTNESS, FanLedBrightness)],
    MODEL_FAN_ZA3: [AttributeEnumMapping(ATTR_LED_BRIGHTNESS, FanLedBrightness)],
    MODEL_FAN_ZA4: [AttributeEnumMapping(ATTR_LED_BRIGHTNESS, FanLedBrightness)],
}

SELECTOR_TYPES = (
    XiaomiMiioSelectDescription(
        key=ATTR_DISPLAY_ORIENTATION,
        attr_name=ATTR_DISPLAY_ORIENTATION,
        name="Display Orientation",
        options_map={
            "Portrait": "Forward",
            "LandscapeLeft": "Left",
            "LandscapeRight": "Right",
        },
        set_method="set_display_orientation",
        set_method_error_message="Setting the display orientation failed.",
        icon="mdi:tablet",
        translation_key="display_orientation",
        options=["forward", "left", "right"],
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioSelectDescription(
        key=ATTR_MODE,
        attr_name=ATTR_MODE,
        name="Mode",
        set_method="set_mode",
        set_method_error_message="Setting the mode of the fan failed.",
        icon="mdi:fan",
        translation_key="airpurifier_mode",
        options=["silent", "auto", "favorite"],
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioSelectDescription(
        key=ATTR_LED_BRIGHTNESS,
        attr_name=ATTR_LED_BRIGHTNESS,
        name="Led Brightness",
        set_method="set_led_brightness",
        set_method_error_message="Setting the led brightness failed.",
        icon="mdi:brightness-6",
        translation_key="led_brightness",
        options=["bright", "dim", "off"],
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioSelectDescription(
        key=ATTR_PTC_LEVEL,
        attr_name=ATTR_PTC_LEVEL,
        name="Auxiliary Heat Level",
        set_method="set_ptc_level",
        set_method_error_message="Setting the ptc level failed.",
        icon="mdi:fire-circle",
        translation_key="ptc_level",
        options=["low", "medium", "high"],
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Selectors from a config entry."""
    if config_entry.data[CONF_FLOW_TYPE] != CONF_DEVICE:
        return

    model = config_entry.data[CONF_MODEL]
    if model not in MODEL_TO_ATTR_MAP:
        return

    entities = []
    unique_id = config_entry.unique_id
    device = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]
    attributes = MODEL_TO_ATTR_MAP[model]

    for description in SELECTOR_TYPES:
        for attribute in attributes:
            if description.key == attribute.attr_name:
                entities.append(
                    XiaomiGenericSelector(
                        device,
                        config_entry,
                        f"{description.key}_{unique_id}",
                        coordinator,
                        description,
                        attribute.enum_class,
                    )
                )

    async_add_entities(entities)


class XiaomiSelector(XiaomiCoordinatedMiioEntity, SelectEntity):
    """Representation of a generic Xiaomi attribute selector."""

    def __init__(self, device, entry, unique_id, coordinator, description):
        """Initialize the generic Xiaomi attribute selector."""
        super().__init__(device, entry, unique_id, coordinator)
        self.entity_description = description


class XiaomiGenericSelector(XiaomiSelector):
    """Representation of a Xiaomi generic selector."""

    entity_description: XiaomiMiioSelectDescription

    def __init__(self, device, entry, unique_id, coordinator, description, enum_class):
        """Initialize the generic Xiaomi attribute selector."""
        super().__init__(device, entry, unique_id, coordinator, description)
        self._current_attr = enum_class(
            self._extract_value_from_attribute(
                self.coordinator.data, self.entity_description.attr_name
            )
        )

        if description.options_map:
            self._options_map = {}
            for key, val in enum_class._member_map_.items():
                self._options_map[description.options_map[key]] = val
        else:
            self._options_map = enum_class._member_map_
        self._reverse_map = {val: key for key, val in self._options_map.items()}
        self._enum_class = enum_class

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        try:
            value = self._extract_value_from_attribute(
                self.coordinator.data, self.entity_description.attr_name
            )
            attr = self._enum_class(value)
        except ValueError:  # if the value does not exist in
            _LOGGER.debug(
                "Value '%s' does not exist in enum %s", value, self._enum_class
            )
            attr = None

        if attr is not None:
            self._current_attr = attr
            self.async_write_ha_state()

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        option = self._reverse_map.get(self._current_attr)
        if option is not None:
            return option.lower()
        return None

    async def async_select_option(self, option: str) -> None:
        """Set an option of the miio device."""
        await self.async_set_attr(option.title())

    async def async_set_attr(self, attr_value: str):
        """Set attr."""
        method = getattr(self._device, self.entity_description.set_method)
        if await self._try_command(
            self.entity_description.set_method_error_message,
            method,
            self._enum_class(self._options_map[attr_value]),
        ):
            self._current_attr = self._options_map[attr_value]
            self.async_write_ha_state()
