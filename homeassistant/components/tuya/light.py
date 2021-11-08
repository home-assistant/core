"""Support for the Tuya lights."""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    COLOR_MODE_ONOFF,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_CONFIG
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import IntegerTypeData, TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode, WorkMode
from .util import remap_value


@dataclass
class TuyaLightEntityDescription(LightEntityDescription):
    """Describe an Tuya light entity."""

    brightness_max: DPCode | None = None
    brightness_min: DPCode | None = None
    brightness: DPCode | tuple[DPCode, ...] | None = None
    color_data: DPCode | tuple[DPCode, ...] | None = None
    color_mode: DPCode | None = None
    color_temp: DPCode | tuple[DPCode, ...] | None = None


LIGHTS: dict[str, tuple[TuyaLightEntityDescription, ...]] = {
    # String Lights
    # https://developer.tuya.com/en/docs/iot/dc?id=Kaof7taxmvadu
    "dc": (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_temp=DPCode.TEMP_VALUE,
            color_data=DPCode.COLOUR_DATA,
        ),
    ),
    # Strip Lights
    # https://developer.tuya.com/en/docs/iot/dd?id=Kaof804aibg2l
    "dd": (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_temp=DPCode.TEMP_VALUE,
            color_data=DPCode.COLOUR_DATA,
        ),
    ),
    # Light
    # https://developer.tuya.com/en/docs/iot/categorydj?id=Kaiuyzy3eheyy
    "dj": (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            color_mode=DPCode.WORK_MODE,
            brightness=(DPCode.BRIGHT_VALUE_V2, DPCode.BRIGHT_VALUE),
            color_temp=(DPCode.TEMP_VALUE_V2, DPCode.TEMP_VALUE),
            color_data=(DPCode.COLOUR_DATA_V2, DPCode.COLOUR_DATA),
        ),
    ),
    # Ceiling Fan Light
    # https://developer.tuya.com/en/docs/iot/fsd?id=Kaof8eiei4c2v
    "fsd": (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_temp=DPCode.TEMP_VALUE,
            color_data=DPCode.COLOUR_DATA,
        ),
    ),
    # Ambient Light
    # https://developer.tuya.com/en/docs/iot/ambient-light?id=Kaiuz06amhe6g
    "fwd": (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_temp=DPCode.TEMP_VALUE,
            color_data=DPCode.COLOUR_DATA,
        ),
    ),
    # Motion Sensor Light
    # https://developer.tuya.com/en/docs/iot/gyd?id=Kaof8a8hycfmy
    "gyd": (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_temp=DPCode.TEMP_VALUE,
            color_data=DPCode.COLOUR_DATA,
        ),
    ),
    # Humidifier Light
    # https://developer.tuya.com/en/docs/iot/categoryjsq?id=Kaiuz1smr440b
    "jsq": (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_data=DPCode.COLOUR_DATA_HSV,
        ),
    ),
    # Switch
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "kg": (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_BACKLIGHT,
            name="Backlight",
        ),
    ),
    # Air conditioner
    # https://developer.tuya.com/en/docs/iot/categorykt?id=Kaiuz0z71ov2n
    "kt": (
        TuyaLightEntityDescription(
            key=DPCode.LIGHT,
            name="Backlight",
        ),
    ),
    # Smart Camera
    # https://developer.tuya.com/en/docs/iot/categorysp?id=Kaiuz35leyo12
    "sp": (
        TuyaLightEntityDescription(
            key=DPCode.FLOODLIGHT_SWITCH,
            brightness=DPCode.FLOODLIGHT_LIGHTNESS,
            name="Floodlight",
        ),
        TuyaLightEntityDescription(
            key=DPCode.BASIC_INDICATOR,
            name="Indicator Light",
            entity_category=ENTITY_CATEGORY_CONFIG,
        ),
    ),
    # Dimmer Switch
    # https://developer.tuya.com/en/docs/iot/categorytgkg?id=Kaiuz0ktx7m0o
    "tgkg": (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED_1,
            name="Light",
            brightness=DPCode.BRIGHT_VALUE_1,
            brightness_max=DPCode.BRIGHTNESS_MAX_1,
            brightness_min=DPCode.BRIGHTNESS_MIN_1,
        ),
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED_2,
            name="Light 2",
            brightness=DPCode.BRIGHT_VALUE_2,
            brightness_max=DPCode.BRIGHTNESS_MAX_2,
            brightness_min=DPCode.BRIGHTNESS_MIN_2,
        ),
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED_3,
            name="Light 3",
            brightness=DPCode.BRIGHT_VALUE_3,
            brightness_max=DPCode.BRIGHTNESS_MAX_3,
            brightness_min=DPCode.BRIGHTNESS_MIN_3,
        ),
    ),
    # Dimmer
    # https://developer.tuya.com/en/docs/iot/tgq?id=Kaof8ke9il4k4
    "tgq": (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            name="Light",
            brightness=(DPCode.BRIGHT_VALUE_V2, DPCode.BRIGHT_VALUE),
            brightness_max=DPCode.BRIGHTNESS_MAX_1,
            brightness_min=DPCode.BRIGHTNESS_MIN_1,
        ),
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED_1,
            name="Light",
            brightness=DPCode.BRIGHT_VALUE_1,
        ),
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED_2,
            name="Light 2",
            brightness=DPCode.BRIGHT_VALUE_2,
        ),
    ),
    # Solar Light
    # https://developer.tuya.com/en/docs/iot/tynd?id=Kaof8j02e1t98
    "tyndj": (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_temp=DPCode.TEMP_VALUE,
            color_data=DPCode.COLOUR_DATA,
        ),
    ),
    # Ceiling Light
    # https://developer.tuya.com/en/docs/iot/ceiling-light?id=Kaiuz03xxfc4r
    "xdd": (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_LED,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_VALUE,
            color_temp=DPCode.TEMP_VALUE,
            color_data=DPCode.COLOUR_DATA,
        ),
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_NIGHT_LIGHT,
            name="Night Light",
        ),
    ),
    # Remote Control
    # https://developer.tuya.com/en/docs/iot/ykq?id=Kaof8ljn81aov
    "ykq": (
        TuyaLightEntityDescription(
            key=DPCode.SWITCH_CONTROLLER,
            color_mode=DPCode.WORK_MODE,
            brightness=DPCode.BRIGHT_CONTROLLER,
            color_temp=DPCode.TEMP_CONTROLLER,
        ),
    ),
}

# Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
LIGHTS["cz"] = LIGHTS["kg"]

# Power Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
LIGHTS["pc"] = LIGHTS["kg"]


@dataclass
class ColorTypeData:
    """Color Type Data."""

    h_type: IntegerTypeData
    s_type: IntegerTypeData
    v_type: IntegerTypeData


DEFAULT_COLOR_TYPE_DATA = ColorTypeData(
    h_type=IntegerTypeData(min=1, scale=0, max=360, step=1),
    s_type=IntegerTypeData(min=1, scale=0, max=255, step=1),
    v_type=IntegerTypeData(min=1, scale=0, max=255, step=1),
)

DEFAULT_COLOR_TYPE_DATA_V2 = ColorTypeData(
    h_type=IntegerTypeData(min=1, scale=0, max=360, step=1),
    s_type=IntegerTypeData(min=1, scale=0, max=1000, step=1),
    v_type=IntegerTypeData(min=1, scale=0, max=1000, step=1),
)


@dataclass
class ColorData:
    """Color Data."""

    type_data: ColorTypeData
    h_value: int
    s_value: int
    v_value: int

    @property
    def hs_color(self) -> tuple[float, float]:
        """Get the HS value from this color data."""
        return (
            self.type_data.h_type.remap_value_to(self.h_value, 0, 360),
            self.type_data.s_type.remap_value_to(self.s_value, 0, 100),
        )

    @property
    def brightness(self) -> int:
        """Get the brightness value from this color data."""
        return round(self.type_data.v_type.remap_value_to(self.v_value, 0, 255))


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya light dynamically through tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]):
        """Discover and add a discovered tuya light."""
        entities: list[TuyaLightEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if descriptions := LIGHTS.get(device.category):
                for description in descriptions:
                    if (
                        description.key in device.function
                        or description.key in device.status
                    ):
                        entities.append(
                            TuyaLightEntity(
                                device, hass_data.device_manager, description
                            )
                        )

        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaLightEntity(TuyaEntity, LightEntity):
    """Tuya light device."""

    entity_description: TuyaLightEntityDescription
    _brightness_dpcode: DPCode | None = None
    _brightness_max_type: IntegerTypeData | None = None
    _brightness_min_type: IntegerTypeData | None = None
    _brightness_type: IntegerTypeData | None = None
    _color_data_dpcode: DPCode | None = None
    _color_data_type: ColorTypeData | None = None
    _color_temp_dpcode: DPCode | None = None
    _color_temp_type: IntegerTypeData | None = None

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: TuyaLightEntityDescription,
    ) -> None:
        """Init TuyaHaLight."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        self._attr_supported_color_modes = {COLOR_MODE_ONOFF}

        # Determine brightness DPCodes
        if (
            isinstance(description.brightness, DPCode)
            and description.brightness in device.function
        ):
            self._brightness_dpcode = description.brightness
        elif isinstance(description.brightness, tuple):
            self._brightness_dpcode = next(
                (
                    dpcode
                    for dpcode in description.brightness
                    if dpcode in device.function
                ),
                None,
            )

        # Determine DPCodes for color temperature
        if (
            isinstance(description.color_temp, DPCode)
            and description.color_temp in device.function
        ):
            self._color_temp_dpcode = description.color_temp
        elif isinstance(description.color_temp, tuple):
            self._color_temp_dpcode = next(
                (
                    dpcode
                    for dpcode in description.color_temp
                    if dpcode in device.function
                ),
                None,
            )

        # Determine DPCodes for color data
        if (
            isinstance(description.color_data, DPCode)
            and description.color_data in device.function
        ):
            self._color_data_dpcode = description.color_data
        elif isinstance(description.color_data, tuple):
            self._color_data_dpcode = next(
                (
                    dpcode
                    for dpcode in description.color_data
                    if dpcode in device.function
                ),
                None,
            )

        # Update internals based on found brightness dpcode
        if self._brightness_dpcode:
            self._attr_supported_color_modes.add(COLOR_MODE_BRIGHTNESS)
            self._brightness_type = IntegerTypeData.from_json(
                device.status_range[self._brightness_dpcode].values
            )

            # Check if min/max capable
            if (
                description.brightness_max is not None
                and description.brightness_min is not None
                and description.brightness_max in device.function
                and description.brightness_min in device.function
            ):
                self._brightness_max_type = IntegerTypeData.from_json(
                    device.status_range[description.brightness_max].values
                )
                self._brightness_min_type = IntegerTypeData.from_json(
                    device.status_range[description.brightness_min].values
                )

        # Update internals based on found color temperature dpcode
        if self._color_temp_dpcode:
            self._attr_supported_color_modes.add(COLOR_MODE_COLOR_TEMP)
            self._color_temp_type = IntegerTypeData.from_json(
                device.status_range[self._color_temp_dpcode].values
            )

        # Update internals based on found color data dpcode
        if self._color_data_dpcode:
            self._attr_supported_color_modes.add(COLOR_MODE_HS)
            # Fetch color data type information
            if function_data := json.loads(
                self.device.function[self._color_data_dpcode].values
            ):
                self._color_data_type = ColorTypeData(
                    h_type=IntegerTypeData(**function_data["h"]),
                    s_type=IntegerTypeData(**function_data["s"]),
                    v_type=IntegerTypeData(**function_data["v"]),
                )
            else:
                # If no type is found, use a default one
                self._color_data_type = DEFAULT_COLOR_TYPE_DATA
                if self._color_data_dpcode == DPCode.COLOUR_DATA_V2 or (
                    self._brightness_type and self._brightness_type.max > 255
                ):
                    self._color_data_type = DEFAULT_COLOR_TYPE_DATA_V2

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.device.status.get(self.entity_description.key, False)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on or control the light."""
        commands = [{"code": self.entity_description.key, "value": True}]

        if self._color_temp_type and ATTR_COLOR_TEMP in kwargs:
            if color_mode_dpcode := self.entity_description.color_mode:
                commands += [
                    {
                        "code": color_mode_dpcode,
                        "value": WorkMode.WHITE,
                    },
                ]

            commands += [
                {
                    "code": self._color_temp_dpcode,
                    "value": round(
                        self._color_temp_type.remap_value_from(
                            kwargs[ATTR_COLOR_TEMP],
                            self.min_mireds,
                            self.max_mireds,
                            reverse=True,
                        )
                    ),
                },
            ]
        elif self._color_data_type and (
            ATTR_HS_COLOR in kwargs
            or (ATTR_BRIGHTNESS in kwargs and self.color_mode == COLOR_MODE_HS)
        ):
            if color_mode_dpcode := self.entity_description.color_mode:
                commands += [
                    {
                        "code": color_mode_dpcode,
                        "value": WorkMode.COLOUR,
                    },
                ]

            if not (brightness := kwargs.get(ATTR_BRIGHTNESS)):
                brightness = self.brightness or 0

            if not (color := kwargs.get(ATTR_HS_COLOR)):
                color = self.hs_color or (0, 0)

            commands += [
                {
                    "code": self._color_data_dpcode,
                    "value": json.dumps(
                        {
                            "h": round(
                                self._color_data_type.h_type.remap_value_from(
                                    color[0], 0, 360
                                )
                            ),
                            "s": round(
                                self._color_data_type.s_type.remap_value_from(
                                    color[1], 0, 100
                                )
                            ),
                            "v": round(
                                self._color_data_type.v_type.remap_value_from(
                                    brightness
                                )
                            ),
                        }
                    ),
                },
            ]

        if (
            ATTR_BRIGHTNESS in kwargs
            and self.color_mode != COLOR_MODE_HS
            and self._brightness_type
        ):
            brightness = kwargs[ATTR_BRIGHTNESS]

            # If there is a min/max value, the brightness is actually limited.
            # Meaning it is actually not on a 0-255 scale.
            if (
                self._brightness_max_type is not None
                and self._brightness_min_type is not None
                and self.entity_description.brightness_max is not None
                and self.entity_description.brightness_min is not None
                and (
                    brightness_max := self.device.status.get(
                        self.entity_description.brightness_max
                    )
                )
                is not None
                and (
                    brightness_min := self.device.status.get(
                        self.entity_description.brightness_min
                    )
                )
                is not None
            ):
                # Remap values onto our scale
                brightness_max = self._brightness_max_type.remap_value_to(
                    brightness_max
                )
                brightness_min = self._brightness_min_type.remap_value_to(
                    brightness_min
                )

                # Remap the brightness value from their min-max to our 0-255 scale
                brightness = remap_value(
                    brightness,
                    to_min=brightness_min,
                    to_max=brightness_max,
                )

            commands += [
                {
                    "code": self._brightness_dpcode,
                    "value": round(self._brightness_type.remap_value_from(brightness)),
                },
            ]

        self._send_command(commands)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        self._send_command([{"code": self.entity_description.key, "value": False}])

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        # If the light is currently in color mode, extract the brightness from the color data
        if self.color_mode == COLOR_MODE_HS and (color_data := self._get_color_data()):
            return color_data.brightness

        if not self._brightness_dpcode or not self._brightness_type:
            return None

        brightness = self.device.status.get(self._brightness_dpcode)
        if brightness is None:
            return None

        # Remap value to our scale
        brightness = self._brightness_type.remap_value_to(brightness)

        # If there is a min/max value, the brightness is actually limited.
        # Meaning it is actually not on a 0-255 scale.
        if (
            self._brightness_max_type is not None
            and self._brightness_min_type is not None
            and self.entity_description.brightness_max is not None
            and self.entity_description.brightness_min is not None
            and (
                brightness_max := self.device.status.get(
                    self.entity_description.brightness_max
                )
            )
            is not None
            and (
                brightness_min := self.device.status.get(
                    self.entity_description.brightness_min
                )
            )
            is not None
        ):
            # Remap values onto our scale
            brightness_max = self._brightness_max_type.remap_value_to(brightness_max)
            brightness_min = self._brightness_min_type.remap_value_to(brightness_min)

            # Remap the brightness value from their min-max to our 0-255 scale
            brightness = remap_value(
                brightness,
                from_min=brightness_min,
                from_max=brightness_max,
            )

        return round(brightness)

    @property
    def color_temp(self) -> int | None:
        """Return the color_temp of the light."""
        if not self._color_temp_dpcode or not self._color_temp_type:
            return None

        temperature = self.device.status.get(self._color_temp_dpcode)
        if temperature is None:
            return None

        return round(
            self._color_temp_type.remap_value_to(
                temperature, self.min_mireds, self.max_mireds, reverse=True
            )
        )

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs_color of the light."""
        if self._color_data_dpcode is None or not (
            color_data := self._get_color_data()
        ):
            return None
        return color_data.hs_color

    @property
    def color_mode(self) -> str:
        """Return the color_mode of the light."""
        # We consider it to be in HS color mode, when work mode is anything
        # else than "white".
        if (
            self.entity_description.color_mode
            and self.device.status.get(self.entity_description.color_mode)
            != WorkMode.WHITE
        ):
            return COLOR_MODE_HS
        if self._color_temp_dpcode:
            return COLOR_MODE_COLOR_TEMP
        if self._brightness_dpcode:
            return COLOR_MODE_BRIGHTNESS
        return COLOR_MODE_ONOFF

    def _get_color_data(self) -> ColorData | None:
        """Get current color data from device."""
        if (
            self._color_data_type is None
            or self._color_data_dpcode is None
            or self._color_data_dpcode not in self.device.status
        ):
            return None

        if not (status_data := self.device.status[self._color_data_dpcode]):
            return None

        if not (status := json.loads(status_data)):
            return None

        return ColorData(
            type_data=self._color_data_type,
            h_value=status["h"],
            s_value=status["s"],
            v_value=status["v"],
        )
