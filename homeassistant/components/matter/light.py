"""Matter light."""

from __future__ import annotations

from typing import Any

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
    filter_supported_color_modes,
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
DEFAULT_TRANSITION = 0.2

# there's a bug in (at least) Espressif's implementation of light transitions
# on devices based on Matter 1.0. Mark potential devices with this issue.
# https://github.com/home-assistant/core/issues/113775
# vendorid (attributeKey 0/40/2)
# productid (attributeKey 0/40/4)
# hw version (attributeKey 0/40/8)
# sw version (attributeKey 0/40/10)
TRANSITION_BLOCKLIST = (
    (4107, 8475, "v1.0", "v1.0"),
    (4107, 8550, "v1.0", "v1.0"),
    (4107, 8551, "v1.0", "v1.0"),
    (4107, 8571, "v1.0", "v1.0"),
    (4107, 8656, "v1.0", "v1.0"),
    (4448, 36866, "V1", "V1.0.0.5"),
    (4456, 1011, "1.0.0", "2.00.00"),
    (4488, 260, "1.0", "1.0.0"),
    (4488, 514, "1.0", "1.0.0"),
    (4921, 42, "1.0", "1.01.060"),
    (4921, 43, "1.0", "1.01.060"),
    (4999, 24875, "1.0", "27.0"),
    (4999, 25057, "1.0", "27.0"),
    (5009, 514, "1.0", "1.0.0"),
    (5010, 769, "3.0", "1.0.0"),
    (5130, 544, "v0.4", "6.7.196e9d4e08-14"),
)


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
    _supports_brightness = False
    _supports_color = False
    _supports_color_temperature = False
    _transitions_disabled = False

    async def _set_xy_color(
        self, xy_color: tuple[float, float], transition: float = 0.0
    ) -> None:
        """Set xy color."""

        matter_xy = convert_to_matter_xy(xy_color)

        await self.send_device_command(
            clusters.ColorControl.Commands.MoveToColor(
                colorX=int(matter_xy[0]),
                colorY=int(matter_xy[1]),
                # transition in matter is measured in tenths of a second
                transitionTime=int(transition * 10),
                # allow setting the color while the light is off,
                # by setting the optionsMask to 1 (=ExecuteIfOff)
                optionsMask=1,
                optionsOverride=1,
            )
        )

    async def _set_hs_color(
        self, hs_color: tuple[float, float], transition: float = 0.0
    ) -> None:
        """Set hs color."""

        matter_hs = convert_to_matter_hs(hs_color)

        await self.send_device_command(
            clusters.ColorControl.Commands.MoveToHueAndSaturation(
                hue=int(matter_hs[0]),
                saturation=int(matter_hs[1]),
                # transition in matter is measured in tenths of a second
                transitionTime=int(transition * 10),
                # allow setting the color while the light is off,
                # by setting the optionsMask to 1 (=ExecuteIfOff)
                optionsMask=1,
                optionsOverride=1,
            )
        )

    async def _set_color_temp(self, color_temp: int, transition: float = 0.0) -> None:
        """Set color temperature."""

        await self.send_device_command(
            clusters.ColorControl.Commands.MoveToColorTemperature(
                colorTemperatureMireds=color_temp,
                # transition in matter is measured in tenths of a second
                transitionTime=int(transition * 10),
                # allow setting the color while the light is off,
                # by setting the optionsMask to 1 (=ExecuteIfOff)
                optionsMask=1,
                optionsOverride=1,
            )
        )

    async def _set_brightness(self, brightness: int, transition: float = 0.0) -> None:
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
                # transition in matter is measured in tenths of a second
                transitionTime=int(transition * 10),
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
        transition = kwargs.get(ATTR_TRANSITION, DEFAULT_TRANSITION)
        if self._transitions_disabled:
            transition = 0

        if self.supported_color_modes is not None:
            if hs_color is not None and ColorMode.HS in self.supported_color_modes:
                await self._set_hs_color(hs_color, transition)
            elif xy_color is not None and ColorMode.XY in self.supported_color_modes:
                await self._set_xy_color(xy_color, transition)
            elif (
                color_temp is not None
                and ColorMode.COLOR_TEMP in self.supported_color_modes
            ):
                await self._set_color_temp(color_temp, transition)

        if brightness is not None and self._supports_brightness:
            await self._set_brightness(brightness, transition)
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
            supported_color_modes = {ColorMode.ONOFF}
            # brightness support
            if self._entity_info.endpoint.has_attribute(
                None, clusters.LevelControl.Attributes.CurrentLevel
            ) and self._entity_info.endpoint.device_types != {device_types.OnOffLight}:
                # We need to filter out the OnOffLight device type here because
                # that can have an optional LevelControl cluster present
                # which we should ignore.
                supported_color_modes.add(ColorMode.BRIGHTNESS)
                self._supports_brightness = True
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
                    self._supports_color = True

                if (
                    capabilities
                    & clusters.ColorControl.Bitmaps.ColorCapabilities.kXYAttributesSupported
                ):
                    supported_color_modes.add(ColorMode.XY)
                    self._supports_color = True

                if (
                    capabilities
                    & clusters.ColorControl.Bitmaps.ColorCapabilities.kColorTemperatureSupported
                ):
                    supported_color_modes.add(ColorMode.COLOR_TEMP)
                    self._supports_color_temperature = True
                    min_mireds = self.get_matter_attribute_value(
                        clusters.ColorControl.Attributes.ColorTempPhysicalMinMireds
                    )
                    if min_mireds > 0:
                        self._attr_min_mireds = min_mireds
                    max_mireds = self.get_matter_attribute_value(
                        clusters.ColorControl.Attributes.ColorTempPhysicalMaxMireds
                    )
                    if min_mireds > 0:
                        self._attr_max_mireds = max_mireds

            supported_color_modes = filter_supported_color_modes(supported_color_modes)
            self._attr_supported_color_modes = supported_color_modes
            self._check_transition_blocklist()
            # flag support for transition as soon as we support setting brightness and/or color
            if (
                supported_color_modes != {ColorMode.ONOFF}
                and not self._transitions_disabled
            ):
                self._attr_supported_features |= LightEntityFeature.TRANSITION

            LOGGER.debug(
                "Supported color modes: %s for %s",
                self._attr_supported_color_modes,
                self.entity_id,
            )

        # set current values
        self._attr_is_on = self.get_matter_attribute_value(
            clusters.OnOff.Attributes.OnOff
        )

        if self._supports_brightness:
            self._attr_brightness = self._get_brightness()

        if self._supports_color_temperature:
            self._attr_color_temp = self._get_color_temperature()

        if self._supports_color:
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
        elif self._attr_color_temp is not None:
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif self._attr_brightness is not None:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_color_mode = ColorMode.ONOFF

    def _check_transition_blocklist(self) -> None:
        """Check if this device is reported to have non working transitions."""
        device_info = self._endpoint.device_info
        if isinstance(device_info, clusters.BridgedDeviceBasicInformation):
            return
        if (
            device_info.vendorID,
            device_info.productID,
            device_info.hardwareVersionString,
            device_info.softwareVersionString,
        ) in TRANSITION_BLOCKLIST:
            self._transitions_disabled = True
            LOGGER.warning(
                "Detected a device that has been reported to have firmware issues "
                "with light transitions. Transitions will be disabled for this light"
            )


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.LIGHT,
        entity_description=LightEntityDescription(
            key="MatterLight", translation_key="light"
        ),
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
            device_types.DimmablePlugInUnit,
            device_types.ExtendedColorLight,
            device_types.OnOffLight,
            device_types.DimmerSwitch,
            device_types.ColorDimmerSwitch,
        ),
    ),
    # Additional schema to match (HS Color) lights with incorrect/missing device type
    MatterDiscoverySchema(
        platform=Platform.LIGHT,
        entity_description=LightEntityDescription(
            key="MatterHSColorLightFallback", translation_key="light"
        ),
        entity_class=MatterLight,
        required_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.ColorControl.Attributes.CurrentHue,
            clusters.ColorControl.Attributes.CurrentSaturation,
        ),
        optional_attributes=(
            clusters.LevelControl.Attributes.CurrentLevel,
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
            key="MatterXYColorLightFallback", translation_key="light"
        ),
        entity_class=MatterLight,
        required_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.ColorControl.Attributes.CurrentX,
            clusters.ColorControl.Attributes.CurrentY,
        ),
        optional_attributes=(
            clusters.LevelControl.Attributes.CurrentLevel,
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
            key="MatterColorTemperatureLightFallback", translation_key="light"
        ),
        entity_class=MatterLight,
        required_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.LevelControl.Attributes.CurrentLevel,
            clusters.ColorControl.Attributes.ColorTemperatureMireds,
        ),
        optional_attributes=(clusters.ColorControl.Attributes.ColorMode,),
    ),
]
