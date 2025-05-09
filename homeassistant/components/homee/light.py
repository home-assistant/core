"""The Homee light platform."""

from typing import Any

from pyHomee.const import AttributeType
from pyHomee.model import HomeeAttribute, HomeeNode

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import (
    brightness_to_value,
    color_hs_to_RGB,
    color_RGB_to_hs,
    value_to_brightness,
)

from . import HomeeConfigEntry
from .const import LIGHT_PROFILES
from .entity import HomeeNodeEntity

LIGHT_ATTRIBUTES = [
    AttributeType.COLOR,
    AttributeType.COLOR_MODE,
    AttributeType.COLOR_TEMPERATURE,
    AttributeType.DIMMING_LEVEL,
]

PARALLEL_UPDATES = 0


def is_light_node(node: HomeeNode) -> bool:
    """Determine if a node is controllable as a homee light based on its profile and attributes."""
    assert node.attribute_map is not None
    return node.profile in LIGHT_PROFILES and AttributeType.ON_OFF in node.attribute_map


def get_color_mode(supported_modes: set[ColorMode]) -> ColorMode:
    """Determine the color mode from the supported modes."""
    if ColorMode.HS in supported_modes:
        return ColorMode.HS
    if ColorMode.COLOR_TEMP in supported_modes:
        return ColorMode.COLOR_TEMP
    if ColorMode.BRIGHTNESS in supported_modes:
        return ColorMode.BRIGHTNESS

    return ColorMode.ONOFF


def get_light_attribute_sets(
    node: HomeeNode,
) -> list[dict[AttributeType, HomeeAttribute]]:
    """Return the lights with their attributes as found in the node."""
    lights: list[dict[AttributeType, HomeeAttribute]] = []
    on_off_attributes = [
        i for i in node.attributes if i.type == AttributeType.ON_OFF and i.editable
    ]
    for a in on_off_attributes:
        attribute_dict: dict[AttributeType, HomeeAttribute] = {a.type: a}
        for attribute in node.attributes:
            if attribute.instance == a.instance and attribute.type in LIGHT_ATTRIBUTES:
                attribute_dict[attribute.type] = attribute
        lights.append(attribute_dict)

    return lights


def rgb_list_to_decimal(color: tuple[int, int, int]) -> int:
    """Convert an rgb color from list to decimal representation."""
    return int(int(color[0]) << 16) + (int(color[1]) << 8) + (int(color[2]))


def decimal_to_rgb_list(color: float) -> list[int]:
    """Convert an rgb color from decimal to list representation."""
    return [
        (int(color) & 0xFF0000) >> 16,
        (int(color) & 0x00FF00) >> 8,
        (int(color) & 0x0000FF),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the Homee platform for the light entity."""

    async_add_entities(
        HomeeLight(node, light, config_entry)
        for node in config_entry.runtime_data.nodes
        for light in get_light_attribute_sets(node)
        if is_light_node(node)
    )


class HomeeLight(HomeeNodeEntity, LightEntity):
    """Representation of a Homee light."""

    def __init__(
        self,
        node: HomeeNode,
        light: dict[AttributeType, HomeeAttribute],
        entry: HomeeConfigEntry,
    ) -> None:
        """Initialize a Homee light."""
        super().__init__(node, entry)

        self._on_off_attr: HomeeAttribute = light[AttributeType.ON_OFF]
        self._dimmer_attr: HomeeAttribute | None = light.get(
            AttributeType.DIMMING_LEVEL
        )
        self._col_attr: HomeeAttribute | None = light.get(AttributeType.COLOR)
        self._temp_attr: HomeeAttribute | None = light.get(
            AttributeType.COLOR_TEMPERATURE
        )
        self._mode_attr: HomeeAttribute | None = light.get(AttributeType.COLOR_MODE)

        self._attr_supported_color_modes = self._get_supported_color_modes()
        self._attr_color_mode = get_color_mode(self._attr_supported_color_modes)

        if self._temp_attr is not None:
            self._attr_min_color_temp_kelvin = int(self._temp_attr.minimum)
            self._attr_max_color_temp_kelvin = int(self._temp_attr.maximum)

        if self._on_off_attr.instance > 0:
            self._attr_translation_key = "light_instance"
            self._attr_translation_placeholders = {
                "instance": str(self._on_off_attr.instance)
            }
        else:
            # If a device has only one light, it will get its name.
            self._attr_name = None
        self._attr_unique_id = (
            f"{entry.runtime_data.settings.uid}-{self._node.id}-{self._on_off_attr.id}"
        )

    @property
    def brightness(self) -> int:
        """Return the brightness of the light."""
        assert self._dimmer_attr is not None
        return value_to_brightness(
            (self._dimmer_attr.minimum + 1, self._dimmer_attr.maximum),
            self._dimmer_attr.current_value,
        )

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the color of the light."""
        assert self._col_attr is not None
        rgb = decimal_to_rgb_list(self._col_attr.current_value)
        return color_RGB_to_hs(*rgb)

    @property
    def color_temp_kelvin(self) -> int:
        """Return the color temperature of the light."""
        assert self._temp_attr is not None
        return int(self._temp_attr.current_value)

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return bool(self._on_off_attr.current_value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        if ATTR_BRIGHTNESS in kwargs and self._dimmer_attr is not None:
            target_value = round(
                brightness_to_value(
                    (self._dimmer_attr.minimum, self._dimmer_attr.maximum),
                    kwargs[ATTR_BRIGHTNESS],
                )
            )
            await self.async_set_homee_value(self._dimmer_attr, target_value)
        else:
            # If no brightness value is given, just turn on.
            await self.async_set_homee_value(self._on_off_attr, 1)

        if ATTR_COLOR_TEMP_KELVIN in kwargs and self._temp_attr is not None:
            await self.async_set_homee_value(
                self._temp_attr, kwargs[ATTR_COLOR_TEMP_KELVIN]
            )
        if ATTR_HS_COLOR in kwargs:
            color = kwargs[ATTR_HS_COLOR]
            if self._col_attr is not None:
                await self.async_set_homee_value(
                    self._col_attr,
                    rgb_list_to_decimal(color_hs_to_RGB(*color)),
                )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self.async_set_homee_value(self._on_off_attr, 0)

    def _get_supported_color_modes(self) -> set[ColorMode]:
        """Determine the supported color modes from the available attributes."""
        color_modes: set[ColorMode] = set()

        if self._temp_attr is not None and self._temp_attr.editable:
            color_modes.add(ColorMode.COLOR_TEMP)
        if self._col_attr is not None:
            color_modes.add(ColorMode.HS)

        # If no other color modes are available, set one of those.
        if len(color_modes) == 0:
            if self._dimmer_attr is not None:
                color_modes.add(ColorMode.BRIGHTNESS)
            else:
                color_modes.add(ColorMode.ONOFF)

        return color_modes
