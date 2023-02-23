"""Matter light."""
from __future__ import annotations

from enum import Enum
from typing import Any

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types

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
from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema
from .util import (
    convert_to_hass_hs,
    convert_to_hass_xy,
    convert_to_matter_hs,
    convert_to_matter_xy,
    renormalize,
)


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


class MatterColorControlFeatures(Enum):
    """Matter color control features."""

    HS = 0  # Hue and saturation (Optional if device is color capable)
    EHUE = 1  # Enhanced hue and saturation (Optional if device is color capable)
    COLOR_LOOP = 2  # Color loop (Optional if device is color capable)
    XY = 3  # XY (Mandatory if device is color capable)
    COLOR_TEMP = 4  # Color temperature (Mandatory if device is color capable)


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

    entity_description: LightEntityDescription

    def _supports_feature(
        self, feature_map: int, feature: MatterColorControlFeatures
    ) -> bool:
        """Return if device supports given feature."""

        return (feature_map & (1 << feature.value)) != 0

    def _supports_color_mode(self, color_feature: MatterColorControlFeatures) -> bool:
        """Return if device supports given color mode."""

        feature_map = self.get_matter_attribute_value(
            clusters.ColorControl.Attributes.FeatureMap,
        )

        assert isinstance(feature_map, int)

        return self._supports_feature(feature_map, color_feature)

    def _supports_hs_color(self) -> bool:
        """Return if device supports hs color."""

        return self._supports_color_mode(MatterColorControlFeatures.HS)

    def _supports_xy_color(self) -> bool:
        """Return if device supports xy color."""

        return self._supports_color_mode(MatterColorControlFeatures.XY)

    def _supports_color_temperature(self) -> bool:
        """Return if device supports color temperature."""

        return self._supports_color_mode(MatterColorControlFeatures.COLOR_TEMP)

    def _supports_brightness(self) -> bool:
        """Return if device supports brightness."""

        return (
            clusters.LevelControl.Attributes.CurrentLevel
            in self._entity_info.attributes_to_watch
        )

    def _supports_color(self) -> bool:
        """Return if device supports color."""

        return (
            clusters.ColorControl.Attributes.ColorMode
            in self._entity_info.attributes_to_watch
        )

    async def _set_xy_color(self, xy_color: tuple[float, float]) -> None:
        """Set xy color."""

        matter_xy = convert_to_matter_xy(xy_color)

        LOGGER.debug("Setting xy color to %s", matter_xy)
        await self.send_device_command(
            clusters.ColorControl.Commands.MoveToColor(
                colorX=int(matter_xy[0]),
                colorY=int(matter_xy[1]),
                # It's required in TLV. We don't implement transition time yet.
                transitionTime=0,
            )
        )

    async def _set_hs_color(self, hs_color: tuple[float, float]) -> None:
        """Set hs color."""

        matter_hs = convert_to_matter_hs(hs_color)

        LOGGER.debug("Setting hs color to %s", matter_hs)
        await self.send_device_command(
            clusters.ColorControl.Commands.MoveToHueAndSaturation(
                hue=int(matter_hs[0]),
                saturation=int(matter_hs[1]),
                # It's required in TLV. We don't implement transition time yet.
                transitionTime=0,
            )
        )

    async def _set_color_temp(self, color_temp: int) -> None:
        """Set color temperature."""

        LOGGER.debug("Setting color temperature to %s", color_temp)
        await self.send_device_command(
            clusters.ColorControl.Commands.MoveToColorTemperature(
                colorTemperature=color_temp,
                # It's required in TLV. We don't implement transition time yet.
                transitionTime=0,
            )
        )

    async def _set_brightness(self, brightness: int) -> None:
        """Set brightness."""

        LOGGER.debug("Setting brightness to %s", brightness)
        level_control = self._endpoint.get_cluster(clusters.LevelControl)

        assert level_control is not None

        level = round(  # type: ignore[unreachable]
            renormalize(
                brightness,
                (0, 255),
                (level_control.minLevel, level_control.maxLevel),
            )
        )

        await self.send_device_command(
            clusters.LevelControl.Commands.MoveToLevelWithOnOff(
                level=level,
                # It's required in TLV. We don't implement transition time yet.
                transitionTime=0,
            )
        )

    def _get_xy_color(self) -> tuple[float, float]:
        """Get xy color from matter."""

        x_color = self.get_matter_attribute_value(
            clusters.ColorControl.Attributes.CurrentX
        )
        y_color = self.get_matter_attribute_value(
            clusters.ColorControl.Attributes.CurrentY
        )

        assert x_color is not None
        assert y_color is not None

        xy_color = convert_to_hass_xy((x_color, y_color))
        LOGGER.debug(
            "Got xy color %s for %s",
            xy_color,
            self._entity_info.primary_attribute,
        )

        return xy_color

    def _get_hs_color(self) -> tuple[float, float]:
        """Get hs color from matter."""

        hue = self.get_matter_attribute_value(
            clusters.ColorControl.Attributes.CurrentHue
        )

        saturation = self.get_matter_attribute_value(
            clusters.ColorControl.Attributes.CurrentSaturation
        )

        assert hue is not None
        assert saturation is not None

        hs_color = convert_to_hass_hs((hue, saturation))

        LOGGER.debug(
            "Got hs color %s for %s",
            hs_color,
            self._entity_info.primary_attribute,
        )

        return hs_color

    def _get_color_temperature(self) -> int:
        """Get color temperature from matter."""

        color_temp = self.get_matter_attribute_value(
            clusters.ColorControl.Attributes.ColorTemperatureMireds
        )

        assert color_temp is not None

        LOGGER.debug(
            "Got color temperature %s for %s",
            color_temp,
            self._entity_info.primary_attribute,
        )

        return int(color_temp)

    def _get_brightness(self) -> int:
        """Get brightness from matter."""

        level_control = self._endpoint.get_cluster(clusters.LevelControl)

        # We should not get here if brightness is not supported.
        assert level_control is not None

        LOGGER.debug(  # type: ignore[unreachable]
            "Got brightness %s for %s",
            level_control.currentLevel,
            self._entity_info.primary_attribute,
        )

        return round(
            renormalize(
                level_control.currentLevel,
                (level_control.minLevel, level_control.maxLevel),
                (0, 255),
            )
        )

    def _get_color_mode(self) -> ColorMode:
        """Get color mode from matter."""

        color_mode = self.get_matter_attribute_value(
            clusters.ColorControl.Attributes.ColorMode
        )

        assert color_mode is not None

        ha_color_mode = COLOR_MODE_MAP[MatterColorMode(color_mode)]

        LOGGER.debug(
            "Got color mode (%s) for %s",
            ha_color_mode,
            self._entity_info.primary_attribute,
        )

        return ha_color_mode

    async def send_device_command(self, command: Any) -> None:
        """Send device command."""
        await self.matter_client.send_device_command(
            node_id=self._endpoint.node.node_id,
            endpoint_id=self._endpoint.endpoint_id,
            command=command,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn light on."""

        hs_color = kwargs.get(ATTR_HS_COLOR)
        xy_color = kwargs.get(ATTR_XY_COLOR)
        color_temp = kwargs.get(ATTR_COLOR_TEMP)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if self._supports_color():
            if hs_color is not None and self._supports_hs_color():
                await self._set_hs_color(hs_color)
            elif xy_color is not None and self._supports_xy_color():
                await self._set_xy_color(xy_color)
            elif color_temp is not None and self._supports_color_temperature():
                await self._set_color_temp(color_temp)

        if brightness is not None and self._supports_brightness():
            await self._set_brightness(brightness)
            return

        await self.send_device_command(
            clusters.OnOff.Commands.On(),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        await self.send_device_command(
            clusters.OnOff.Commands.Off(),
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""

        supports_color = self._supports_color()
        supports_color_temperature = (
            self._supports_color_temperature() if supports_color else False
        )
        supports_brightness = self._supports_brightness()

        if self._attr_supported_color_modes is None:
            supported_color_modes = set()
            if supports_color:
                supported_color_modes.add(ColorMode.XY)
                if self._supports_hs_color():
                    supported_color_modes.add(ColorMode.HS)

            if supports_color_temperature:
                supported_color_modes.add(ColorMode.COLOR_TEMP)

            if supports_brightness:
                supported_color_modes.add(ColorMode.BRIGHTNESS)

            self._attr_supported_color_modes = (
                supported_color_modes if supported_color_modes else None
            )

        LOGGER.debug(
            "Supported color modes: %s for %s",
            self._attr_supported_color_modes,
            self._entity_info.primary_attribute,
        )

        if supports_color:
            self._attr_color_mode = self._get_color_mode()
            if self._attr_color_mode == ColorMode.HS:
                self._attr_hs_color = self._get_hs_color()
            else:
                self._attr_xy_color = self._get_xy_color()

        if supports_color_temperature:
            self._attr_color_temp = self._get_color_temperature()

        self._attr_is_on = self.get_matter_attribute_value(
            clusters.OnOff.Attributes.OnOff
        )

        if supports_brightness:
            self._attr_brightness = self._get_brightness()


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.LIGHT,
        entity_description=LightEntityDescription(key="ExtendedMatterLight"),
        entity_class=MatterLight,
        required_attributes=(clusters.OnOff.Attributes.OnOff,),
        optional_attributes=(
            clusters.LevelControl.Attributes.CurrentLevel,
            clusters.ColorControl.Attributes.ColorMode,
            clusters.ColorControl.Attributes.CurrentHue,
            clusters.ColorControl.Attributes.CurrentSaturation,
            clusters.ColorControl.Attributes.CurrentX,
            clusters.ColorControl.Attributes.CurrentY,
            clusters.ColorControl.Attributes.ColorTemperatureMireds,
        ),
        # restrict device type to prevent discovery in switch platform
        not_device_type=(device_types.OnOffPlugInUnit,),
    ),
]
