"""Matter light."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import partial
from typing import Any

from chip.clusters import Objects as clusters
from matter_server.common.models import device_types

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_XY_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import LOGGER
from .entity import MatterEntity, MatterEntityDescriptionBaseClass
from .helpers import get_matter
from .util import renormalize


class MatterColorMode(Enum):
    """Matter color mode."""

    HS = 0
    XY = 1
    COLOR_TEMP = 2


COLOR_MODE_MAP = {
    MatterColorMode.HS: ColorMode.HS,
    MatterColorMode.XY: ColorMode.XY,
    MatterColorMode.COLOR_TEMP: ColorMode.COLOR_TEMP,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter Light from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.LIGHT, async_add_entities)


class MatterLight(MatterEntity, LightEntity):
    """Representation of a Matter light."""

    entity_description: MatterLightEntityDescription

    def _supports_brightness(self) -> bool:
        """Return if device supports brightness."""
        return (
            clusters.LevelControl.Attributes.CurrentLevel
            in self.entity_description.subscribe_attributes
        )

    def _supports_color_temperature(self) -> bool:
        """Return if device supports color temperature."""
        return (
            clusters.ColorControl.Attributes.ColorTemperatureMireds
            in self.entity_description.subscribe_attributes
        )

    def _supports_color(self) -> bool:
        """Return if device supports color."""
        return (
            clusters.ColorControl.Attributes.ColorMode
            in self.entity_description.subscribe_attributes
        )

    async def send_device_command(self, command: Any) -> None:
        """Send device command."""
        await self.matter_client.send_device_command(
            node_id=self._device_type_instance.node.node_id,
            endpoint=self._device_type_instance.endpoint,
            command=command,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn light on."""

        hs_color = kwargs.get(ATTR_HS_COLOR)
        xy_color = kwargs.get(ATTR_XY_COLOR)
        color_temp = kwargs.get(ATTR_COLOR_TEMP)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if hs_color is not None:
            LOGGER.info("Setting hs color to %s", hs_color)
            await self.matter_client.send_device_command(
                node_id=self._device_type_instance.node.node_id,
                endpoint=self._device_type_instance.endpoint,
                command=clusters.ColorControl.Commands.MoveToHueAndSaturation(
                    hue=round(hs_color[0]),
                    saturation=round(hs_color[1]),
                    # It's required in TLV. We don't implement transition time yet.
                    transitionTime=0,
                ),
            )
        elif xy_color is not None:
            LOGGER.info("Setting xy color to %s", xy_color)
            await self.matter_client.send_device_command(
                node_id=self._device_type_instance.node.node_id,
                endpoint=self._device_type_instance.endpoint,
                command=clusters.ColorControl.Commands.MoveToColor(
                    colorX=round(xy_color[0]),
                    colorY=round(xy_color[1]),
                    # It's required in TLV. We don't implement transition time yet.
                    transitionTime=0,
                ),
            )
        elif color_temp is not None:
            LOGGER.info("Setting color temp to %s", color_temp)
            await self.send_device_command(
                clusters.ColorControl.Commands.MoveToColorTemperature(
                    colorTemperature=color_temp,
                    # It's required in TLV. We don't implement transition time yet.
                    transitionTime=0,
                )
            )

        if not brightness or not self._supports_brightness():
            await self.send_device_command(
                clusters.OnOff.Commands.On(),
            )
            return

        level_control = self._device_type_instance.get_cluster(clusters.LevelControl)
        # We check above that the device supports brightness, ie level control.
        assert level_control is not None

        level = round(
            renormalize(
                kwargs[ATTR_BRIGHTNESS],
                (0, 255),
                (level_control.minLevel, level_control.maxLevel),
            )
        )

        await self.send_device_command(
            clusters.LevelControl.Commands.MoveToLevelWithOnOff(
                level=level,
                # It's required in TLV. We don't implement transition time yet.
                transitionTime=0,
            ),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        await self.matter_client.send_device_command(
            node_id=self._device_type_instance.node.node_id,
            endpoint=self._device_type_instance.endpoint,
            command=clusters.OnOff.Commands.Off(),
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""

        supports_color = self._supports_color()

        if self._attr_supported_color_modes is None and supports_color:
            self._attr_supported_color_modes = {
                ColorMode.XY,
                ColorMode.COLOR_TEMP,
                ColorMode.BRIGHTNESS,
            }

            # Adds HS if supported
            # Feature map:
            # 0: Supports Hue and Saturation (Optional if extended color model is supported)
            # 1: Supports Enhanced Hue and Saturation (Optional if extended color model is supported)
            # 2: Supports Color Loop (Optional if extended color model is supported)
            # 3: Supports XY Color (Mandatory if extended color model is supported)
            # 4: Supports Color Temperature (Mandatory if extended color model is supported)
            if colorcontrol := self._device_type_instance.get_cluster(
                clusters.ColorControl
            ):
                if colorcontrol.featureMap & (1 << 0):
                    self._attr_supported_color_modes.add(ColorMode.HS)

        supports_color_temperature = self._supports_color_temperature()

        if self._attr_supported_color_modes is None and supports_color_temperature:
            self._attr_supported_color_modes = {
                ColorMode.COLOR_TEMP,
                ColorMode.BRIGHTNESS,
            }

        supports_brigthness = self._supports_brightness()

        if self._attr_supported_color_modes is None and supports_brigthness:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

        LOGGER.debug(
            "Supported color modes: %s for %s",
            self._attr_supported_color_modes,
            self._device_type_instance,
        )

        if supports_color:
            color_mode = self.get_matter_attribute(
                clusters.ColorControl.Attributes.ColorMode
            )

            assert color_mode is not None

            self._attr_color_mode = COLOR_MODE_MAP[MatterColorMode(color_mode.value)]
            LOGGER.info(
                "Color mode: %s for %s",
                self._attr_color_mode,
                self._device_type_instance,
            )

            if self._attr_color_mode == ColorMode.HS:
                hue = self.get_matter_attribute(
                    clusters.ColorControl.Attributes.CurrentHue
                )

                saturation = self.get_matter_attribute(
                    clusters.ColorControl.Attributes.CurrentSaturation
                )

                assert hue is not None
                assert saturation is not None

                self._attr_hs_color = (hue.value, saturation.value)
            else:
                xy_color = (
                    self.get_matter_attribute(
                        clusters.ColorControl.Attributes.CurrentX
                    ),
                    self.get_matter_attribute(
                        clusters.ColorControl.Attributes.CurrentY
                    ),
                )

                assert xy_color[0] is not None
                assert xy_color[1] is not None

                self._attr_xy_color = (xy_color[0].value, xy_color[1].value)

        if supports_color_temperature:
            if color_temp := self.get_matter_attribute(
                clusters.ColorControl.Attributes.ColorTemperatureMireds
            ):
                self._attr_color_temp = color_temp.value

        if attr := self.get_matter_attribute(clusters.OnOff.Attributes.OnOff):
            self._attr_is_on = attr.value

        if supports_brigthness:
            level_control = self._device_type_instance.get_cluster(
                clusters.LevelControl
            )
            # We check above that the device supports brightness, ie level control.
            assert level_control is not None

            # Convert brightness to Home Assistant = 0..255
            self._attr_brightness = round(
                renormalize(
                    level_control.currentLevel,
                    (level_control.minLevel, level_control.maxLevel),
                    (0, 255),
                )
            )


@dataclass
class MatterLightEntityDescription(
    LightEntityDescription,
    MatterEntityDescriptionBaseClass,
):
    """Matter light entity description."""


# You can't set default values on inherited data classes
MatterLightEntityDescriptionFactory = partial(
    MatterLightEntityDescription, entity_cls=MatterLight
)

# Mapping of a Matter Device type to Light Entity Description.
# A Matter device type (instance) can consist of multiple attributes.
# For example a Color Light which has an attribute to control brightness
# but also for color.

DEVICE_ENTITY: dict[
    type[device_types.DeviceType],
    MatterEntityDescriptionBaseClass | list[MatterEntityDescriptionBaseClass],
] = {
    device_types.OnOffLight: MatterLightEntityDescriptionFactory(
        key=device_types.OnOffLight,
        subscribe_attributes=(clusters.OnOff.Attributes.OnOff,),
    ),
    device_types.DimmableLight: MatterLightEntityDescriptionFactory(
        key=device_types.DimmableLight,
        subscribe_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.LevelControl.Attributes.CurrentLevel,
        ),
    ),
    device_types.DimmablePlugInUnit: MatterLightEntityDescriptionFactory(
        key=device_types.DimmablePlugInUnit,
        subscribe_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.LevelControl.Attributes.CurrentLevel,
        ),
    ),
    device_types.ColorTemperatureLight: MatterLightEntityDescriptionFactory(
        key=device_types.ColorTemperatureLight,
        subscribe_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.LevelControl.Attributes.CurrentLevel,
            clusters.ColorControl.Attributes.ColorTemperatureMireds,
        ),
    ),
    device_types.ExtendedColorLight: MatterLightEntityDescriptionFactory(
        key=device_types.ExtendedColorLight,
        subscribe_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.LevelControl.Attributes.CurrentLevel,
            clusters.ColorControl.Attributes.ColorMode,
            clusters.ColorControl.Attributes.CurrentHue,
            clusters.ColorControl.Attributes.CurrentSaturation,
            clusters.ColorControl.Attributes.CurrentX,
            clusters.ColorControl.Attributes.CurrentY,
            clusters.ColorControl.Attributes.ColorTemperatureMireds,
        ),
    ),
}
