"""Matter light."""
from __future__ import annotations

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

COLOR_MODE_MAP = {
    clusters.ColorControl.Enums.ColorMode.kCurrentHueAndCurrentSaturation: ColorMode.HS,
    clusters.ColorControl.Enums.ColorMode.kCurrentXAndCurrentY: ColorMode.XY,
    clusters.ColorControl.Enums.ColorMode.kColorTemperature: ColorMode.COLOR_TEMP,
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

    entity_description: LightEntityDescription

    @property
    def supports_color(self) -> bool:
        """Return if the device supports color control."""
        if not self._attr_supported_color_modes:
            return False
        return (
            ColorMode.HS in self._attr_supported_color_modes
            or ColorMode.XY in self._attr_supported_color_modes
        )

    @property
    def supports_color_temperature(self) -> bool:
        """Return if the device supports color temperature control."""
        if not self._attr_supported_color_modes:
            return False
        return ColorMode.COLOR_TEMP in self._attr_supported_color_modes

    @property
    def supports_brightness(self) -> bool:
        """Return if the device supports bridghtness control."""
        if not self._attr_supported_color_modes:
            return False
        return ColorMode.BRIGHTNESS in self._attr_supported_color_modes

    async def _set_xy_color(self, xy_color: tuple[float, float]) -> None:
        """Set xy color."""

        matter_xy = convert_to_matter_xy(xy_color)

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

        await self.send_device_command(
            clusters.ColorControl.Commands.MoveToColorTemperature(
                colorTemperatureMireds=color_temp,
                # It's required in TLV. We don't implement transition time yet.
                transitionTime=0,
            )
        )

    async def _set_brightness(self, brightness: int) -> None:
        """Set brightness."""

        level_control = self._endpoint.get_cluster(clusters.LevelControl)

        assert level_control is not None

        level = round(  # type: ignore[unreachable]
            renormalize(
                brightness,
                (0, 255),
                (level_control.minLevel or 1, level_control.maxLevel or 254),
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
            self.entity_id,
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
            self.entity_id,
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
            self.entity_id,
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
            self.entity_id,
        )

        return round(
            renormalize(
                level_control.currentLevel,
                (level_control.minLevel or 1, level_control.maxLevel or 254),
                (0, 255),
            )
        )

    def _get_color_mode(self) -> ColorMode:
        """Get color mode from matter."""

        color_mode = self.get_matter_attribute_value(
            clusters.ColorControl.Attributes.ColorMode
        )

        assert color_mode is not None

        ha_color_mode = COLOR_MODE_MAP[color_mode]

        LOGGER.debug(
            "Got color mode (%s) for %s",
            ha_color_mode,
            self.entity_id,
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

        if self.supported_color_modes is not None:
            if hs_color is not None and ColorMode.HS in self.supported_color_modes:
                await self._set_hs_color(hs_color)
            elif xy_color is not None and ColorMode.XY in self.supported_color_modes:
                await self._set_xy_color(xy_color)
            elif (
                color_temp is not None
                and ColorMode.COLOR_TEMP in self.supported_color_modes
            ):
                await self._set_color_temp(color_temp)

        if brightness is not None and self.supports_brightness:
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
        if self._attr_supported_color_modes is None:
            # work out what (color)features are supported
            supported_color_modes: set[ColorMode] = set()
            # brightness support
            if self._entity_info.endpoint.has_attribute(
                None, clusters.LevelControl.Attributes.CurrentLevel
            ):
                supported_color_modes.add(ColorMode.BRIGHTNESS)
            # colormode(s)
            if self._entity_info.endpoint.has_attribute(
                None, clusters.ColorControl.Attributes.ColorMode
            ) and self._entity_info.endpoint.has_attribute(
                None, clusters.ColorControl.Attributes.ColorCapabilities
            ):
                capabilities = self.get_matter_attribute_value(
                    clusters.ColorControl.Attributes.ColorCapabilities
                )

                assert capabilities is not None

                if (
                    capabilities
                    & clusters.ColorControl.Bitmaps.ColorCapabilities.kHueSaturationSupported
                ):
                    supported_color_modes.add(ColorMode.HS)

                if (
                    capabilities
                    & clusters.ColorControl.Bitmaps.ColorCapabilities.kXYAttributesSupported
                ):
                    supported_color_modes.add(ColorMode.XY)

                if (
                    capabilities
                    & clusters.ColorControl.Bitmaps.ColorCapabilities.kColorTemperatureSupported
                ):
                    supported_color_modes.add(ColorMode.COLOR_TEMP)

            self._attr_supported_color_modes = supported_color_modes

            LOGGER.debug(
                "Supported color modes: %s for %s",
                self._attr_supported_color_modes,
                self.entity_id,
            )

        # set current values

        if self.supports_color:
            self._attr_color_mode = color_mode = self._get_color_mode()
            if (
                ColorMode.HS in self._attr_supported_color_modes
                and color_mode == ColorMode.HS
            ):
                self._attr_hs_color = self._get_hs_color()
            elif (
                ColorMode.XY in self._attr_supported_color_modes
                and color_mode == ColorMode.XY
            ):
                self._attr_xy_color = self._get_xy_color()

        if self.supports_color_temperature:
            self._attr_color_temp = self._get_color_temperature()

        self._attr_is_on = self.get_matter_attribute_value(
            clusters.OnOff.Attributes.OnOff
        )

        if self.supports_brightness:
            self._attr_brightness = self._get_brightness()


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.LIGHT,
        entity_description=LightEntityDescription(key="MatterLight", name=None),
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
        device_type=(
            device_types.ColorTemperatureLight,
            device_types.DimmableLight,
            device_types.ExtendedColorLight,
            device_types.OnOffLight,
        ),
    ),
    # Additional schema to match (HS Color) lights with incorrect/missing device type
    MatterDiscoverySchema(
        platform=Platform.LIGHT,
        entity_description=LightEntityDescription(
            key="MatterHSColorLightFallback", name=None
        ),
        entity_class=MatterLight,
        required_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.LevelControl.Attributes.CurrentLevel,
            clusters.ColorControl.Attributes.CurrentHue,
            clusters.ColorControl.Attributes.CurrentSaturation,
        ),
        optional_attributes=(
            clusters.ColorControl.Attributes.ColorTemperatureMireds,
            clusters.ColorControl.Attributes.ColorMode,
            clusters.ColorControl.Attributes.CurrentX,
            clusters.ColorControl.Attributes.CurrentY,
        ),
    ),
    # Additional schema to match (XY Color) lights with incorrect/missing device type
    MatterDiscoverySchema(
        platform=Platform.LIGHT,
        entity_description=LightEntityDescription(
            key="MatterXYColorLightFallback", name=None
        ),
        entity_class=MatterLight,
        required_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.LevelControl.Attributes.CurrentLevel,
            clusters.ColorControl.Attributes.CurrentX,
            clusters.ColorControl.Attributes.CurrentY,
        ),
        optional_attributes=(
            clusters.ColorControl.Attributes.ColorTemperatureMireds,
            clusters.ColorControl.Attributes.ColorMode,
            clusters.ColorControl.Attributes.CurrentHue,
            clusters.ColorControl.Attributes.CurrentSaturation,
        ),
    ),
    # Additional schema to match (color temperature) lights with incorrect/missing device type
    MatterDiscoverySchema(
        platform=Platform.LIGHT,
        entity_description=LightEntityDescription(
            key="MatterColorTemperatureLightFallback", name=None
        ),
        entity_class=MatterLight,
        required_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.LevelControl.Attributes.CurrentLevel,
            clusters.ColorControl.Attributes.ColorTemperatureMireds,
        ),
        optional_attributes=(clusters.ColorControl.Attributes.ColorMode,),
    ),
    # Additional schema to match generic dimmable lights with incorrect/missing device type
    MatterDiscoverySchema(
        platform=Platform.LIGHT,
        entity_description=LightEntityDescription(
            key="MatterDimmableLightFallback", name=None
        ),
        entity_class=MatterLight,
        required_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.LevelControl.Attributes.CurrentLevel,
        ),
        optional_attributes=(
            clusters.ColorControl.Attributes.ColorMode,
            clusters.ColorControl.Attributes.CurrentHue,
            clusters.ColorControl.Attributes.CurrentSaturation,
            clusters.ColorControl.Attributes.CurrentX,
            clusters.ColorControl.Attributes.CurrentY,
            clusters.ColorControl.Attributes.ColorTemperatureMireds,
        ),
        # important: make sure to rule out all device types that are also based on the
        # onoff and levelcontrol clusters !
        not_device_type=(
            device_types.Fan,
            device_types.GenericSwitch,
            device_types.OnOffPlugInUnit,
            device_types.HeatingCoolingUnit,
            device_types.Pump,
            device_types.CastingVideoClient,
            device_types.VideoRemoteControl,
            device_types.Speaker,
        ),
    ),
]
