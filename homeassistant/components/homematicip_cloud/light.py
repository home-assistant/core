"""Support for HomematicIP Cloud lights."""

import logging
from typing import Any, override

from homematicip.base.enums import (
    FunctionalChannelType,
    OpticalSignalBehaviour,
    RGBColorState,
)
from homematicip.base.functionalChannels import (
    FunctionalChannel,
    NotificationLightChannel,
    NotificationMp3SoundChannel,
)
from homematicip.device import Device
from packaging.version import Version

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_NAME,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LIGHT_OWNED_DEVICE_TYPES, SWITCH_CHANNEL_TYPES
from .entity import HomematicipGenericEntity
from .hap import HomematicIPConfigEntry, HomematicipHAP

_logger = logging.getLogger(__name__)

DIMMER_CHANNEL_TYPES = (
    FunctionalChannelType.DIMMER_CHANNEL,
    FunctionalChannelType.MULTI_MODE_INPUT_DIMMER_CHANNEL,
)

# the HmIP-BSL names its two signal lamps by position
NOTIFICATION_LIGHT_POSITIONS = {2: "Top", 3: "Bottom"}


def _channels(
    device: Device, channel_types: tuple[FunctionalChannelType, ...]
) -> list[FunctionalChannel]:
    """Return the channels of a device with one of the given types."""
    return [
        channel
        for channel in device.functionalChannels
        if channel.functionalChannelType in channel_types
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomematicIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP Cloud lights from a config entry."""
    hap = config_entry.runtime_data
    entities: list[HomematicipGenericEntity] = []

    for device in hap.home.devices:
        if getattr(device, "deviceType", None) in LIGHT_OWNED_DEVICE_TYPES:
            entities.extend(
                HomematicipLight(hap, device, channel.index)
                for channel in _channels(device, SWITCH_CHANNEL_TYPES)
            )

        dimmer_channels = _channels(device, DIMMER_CHANNEL_TYPES)
        # a lone channel is the device itself, so it keeps the device name
        is_multi_channel = len(dimmer_channels) > 1
        entities.extend(
            HomematicipDimmer(hap, device, channel.index, is_multi_channel)
            for channel in dimmer_channels
        )

        if notification_channels := _channels(
            device, (FunctionalChannelType.NOTIFICATION_LIGHT_CHANNEL,)
        ):
            entity_class = (
                HomematicipNotificationLightV2
                if Version(device.firmwareVersion) > Version("2.0.0")
                else HomematicipNotificationLight
            )
            entities.extend(
                entity_class(
                    hap,
                    device,
                    channel.index,
                    NOTIFICATION_LIGHT_POSITIONS.get(channel.index),
                )
                for channel in notification_channels
            )

        entities.extend(
            HomematicipColorLight(hap, device, channel.index)
            for channel in _channels(
                device, (FunctionalChannelType.UNIVERSAL_LIGHT_CHANNEL,)
            )
        )
        entities.extend(
            HomematicipCombinationSignallingLight(hap, device, channel.index)
            for channel in _channels(
                device, (FunctionalChannelType.NOTIFICATION_MP3_SOUND_CHANNEL,)
            )
        )

        optical_channels = sorted(
            _channels(device, (FunctionalChannelType.OPTICAL_SIGNAL_CHANNEL,)),
            key=lambda ch: ch.index,
        )
        entities.extend(
            HomematicipOpticalSignalLight(hap, device, channel.index, led_number)
            for led_number, channel in enumerate(optical_channels, start=1)
        )

    async_add_entities(entities)


class HomematicipLight(HomematicipGenericEntity, LightEntity):
    """Representation of the HomematicIP light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, hap: HomematicipHAP, device, channel: int) -> None:
        """Initialize the light entity."""
        super().__init__(
            hap,
            device,
            channel=channel,
            channel_real_index=channel,
            feature_id="light",
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.get_channel_or_raise().on

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self.get_channel_or_raise().async_turn_on()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.get_channel_or_raise().async_turn_off()


class HomematicipColorLight(HomematicipGenericEntity, LightEntity):
    """Representation of the HomematicIP color light."""

    def __init__(self, hap: HomematicipHAP, device: Device, channel_index: int) -> None:
        """Initialize the light entity."""
        super().__init__(
            hap,
            device,
            channel=channel_index,
            is_multi_channel=True,
            channel_real_index=channel_index,
            feature_id="color_light",
        )

    def _supports_color(self) -> bool:
        """Return true if device supports hue/saturation color control."""
        channel = self.get_channel_or_raise()
        return channel.hue is not None and channel.saturationLevel is not None

    @property
    @override
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if self._supports_color():
            return ColorMode.HS
        return ColorMode.BRIGHTNESS

    @property
    @override
    def supported_color_modes(self) -> set[ColorMode]:
        """Return the supported color modes."""
        if self._supports_color():
            return {ColorMode.HS}
        return {ColorMode.BRIGHTNESS}

    @property
    @override
    def is_on(self) -> bool:
        """Return true if light is on."""
        channel = self.get_channel_or_raise()
        return channel.on

    @property
    @override
    def brightness(self) -> int | None:
        """Return the current brightness."""
        channel = self.get_channel_or_raise()
        return int(channel.dimLevel * 255.0)

    @property
    @override
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        channel = self.get_channel_or_raise()
        if channel.hue is None or channel.saturationLevel is None:
            return None
        return (
            channel.hue,
            channel.saturationLevel * 100.0,
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        channel = self.get_channel_or_raise()
        dim_level = round(kwargs.get(ATTR_BRIGHTNESS, 255) / 255.0, 2)

        if ATTR_BRIGHTNESS not in kwargs:
            # If no brightness is set, use the current brightness
            dim_level = channel.dimLevel or 1.0

        # Use dim-only method for monochrome mode (hue/saturation not supported)
        if not self._supports_color():
            await channel.set_dim_level_async(dim_level=dim_level)
            return

        # Full color mode with hue/saturation
        if ATTR_HS_COLOR in kwargs:
            hs_color = kwargs[ATTR_HS_COLOR]
            hue = hs_color[0] % 360.0
            saturation = hs_color[1] / 100.0
        else:
            hue = channel.hue
            saturation = channel.saturationLevel

        await channel.set_hue_saturation_dim_level_async(
            hue=hue, saturation_level=saturation, dim_level=dim_level
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        channel = self.get_channel_or_raise()
        await channel.set_switch_state_async(on=False)


class HomematicipDimmer(HomematicipGenericEntity, LightEntity):
    """Representation of HomematicIP Cloud dimmer."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        hap: HomematicipHAP,
        device,
        channel: int,
        is_multi_channel: bool,
    ) -> None:
        """Initialize the dimmer light entity."""
        super().__init__(
            hap,
            device,
            channel=channel,
            is_multi_channel=is_multi_channel,
            channel_real_index=channel,
            feature_id="dimmer",
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true if dimmer is on."""
        dim_level = self.get_channel_or_raise().dimLevel
        return dim_level is not None and dim_level > 0.0

    @property
    @override
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int((self.get_channel_or_raise().dimLevel or 0.0) * 255)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the dimmer on."""
        channel = self.get_channel_or_raise()
        if ATTR_BRIGHTNESS in kwargs:
            await channel.async_set_dim_level(kwargs[ATTR_BRIGHTNESS] / 255.0)
        else:
            await channel.async_set_dim_level(1)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the dimmer off."""
        await self.get_channel_or_raise().async_set_dim_level(0)


class HomematicipNotificationLight(HomematicipGenericEntity, LightEntity):
    """Representation of HomematicIP Cloud notification light."""

    _attr_color_mode = ColorMode.HS
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_supported_features = LightEntityFeature.TRANSITION

    def __init__(
        self, hap: HomematicipHAP, device, channel: int, post: str | None
    ) -> None:
        """Initialize the notification light entity."""
        super().__init__(
            hap,
            device,
            post=post,
            channel=channel,
            is_multi_channel=True,
            channel_real_index=channel,
            feature_id="notification_light",
        )

        self._color_switcher: dict[str, tuple[float, float]] = {
            RGBColorState.WHITE: (0.0, 0.0),
            RGBColorState.RED: (0.0, 100.0),
            RGBColorState.YELLOW: (60.0, 100.0),
            RGBColorState.GREEN: (120.0, 100.0),
            RGBColorState.TURQUOISE: (180.0, 100.0),
            RGBColorState.BLUE: (240.0, 100.0),
            RGBColorState.PURPLE: (300.0, 100.0),
        }

    @property
    def _func_channel(self) -> NotificationLightChannel:
        return self.get_channel_or_raise()

    @property
    @override
    def is_on(self) -> bool:
        """Return true if light is on."""
        return (
            self._func_channel.dimLevel is not None
            and self._func_channel.dimLevel > 0.0
        )

    @property
    @override
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int((self._func_channel.dimLevel or 0.0) * 255)

    @property
    @override
    def hs_color(self) -> tuple[float, float]:
        """Return the hue and saturation color value [float, float]."""
        simple_rgb_color = self._func_channel.simpleRGBColorState
        return self._color_switcher.get(simple_rgb_color, (0.0, 0.0))

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the notification light sensor."""
        state_attr = super().extra_state_attributes

        if self.is_on:
            state_attr[ATTR_COLOR_NAME] = self._func_channel.simpleRGBColorState

        return state_attr

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # Use hs_color from kwargs,
        # if not applicable use current hs_color.
        hs_color = kwargs.get(ATTR_HS_COLOR, self.hs_color)
        simple_rgb_color = _convert_color(hs_color)

        # Use brightness from kwargs,
        # if not applicable use current brightness.
        brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness)

        # If no kwargs, use default value.
        if not kwargs:
            brightness = 255

        # Minimum brightness is 10, otherwise the led is disabled
        brightness = max(10, brightness)
        dim_level = brightness / 255.0
        transition = kwargs.get(ATTR_TRANSITION, 0.5)

        await self._func_channel.async_set_rgb_dim_level_with_time(
            rgb=simple_rgb_color,
            dimLevel=dim_level,
            onTime=0,
            rampTime=transition,
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        simple_rgb_color = self._func_channel.simpleRGBColorState
        transition = kwargs.get(ATTR_TRANSITION, 0.5)

        await self._func_channel.async_set_rgb_dim_level_with_time(
            rgb=simple_rgb_color,
            dimLevel=0.0,
            onTime=0,
            rampTime=transition,
        )


class HomematicipNotificationLightV2(HomematicipNotificationLight, LightEntity):
    """Representation of HomematicIP Cloud notification light."""

    _effect_list = [
        OpticalSignalBehaviour.BILLOW_MIDDLE,
        OpticalSignalBehaviour.BLINKING_MIDDLE,
        OpticalSignalBehaviour.FLASH_MIDDLE,
        OpticalSignalBehaviour.OFF,
        OpticalSignalBehaviour.ON,
    ]

    def __init__(
        self, hap: HomematicipHAP, device, channel: int, post: str | None
    ) -> None:
        """Initialize the notification light entity."""
        super().__init__(hap, device, post=post, channel=channel)
        self._attr_supported_features |= LightEntityFeature.EFFECT

    @property
    @override
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self._effect_list

    @property
    @override
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._func_channel.opticalSignalBehaviour

    @property
    @override
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._func_channel.on

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # Use hs_color from kwargs,
        # if not applicable use current hs_color.
        hs_color = kwargs.get(ATTR_HS_COLOR, self.hs_color)
        simple_rgb_color = _convert_color(hs_color)

        # If no kwargs, use default value.
        brightness = 255
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]

        # Minimum brightness is 10, otherwise the led is disabled
        brightness = max(10, brightness)
        dim_level = round(brightness / 255.0, 2)

        effect = self.effect
        if ATTR_EFFECT in kwargs:
            effect = kwargs[ATTR_EFFECT]

        await self._func_channel.async_set_optical_signal(
            opticalSignalBehaviour=effect, rgb=simple_rgb_color, dimLevel=dim_level
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._func_channel.async_turn_off()


def _convert_color(color: tuple) -> RGBColorState:
    """Convert the given color to the reduced RGBColorState color.

    RGBColorStat contains only 8 colors including white and black,
    so a conversion is required.
    """
    if color is None:
        return RGBColorState.WHITE

    hue = int(color[0])
    saturation = int(color[1])
    if saturation < 5:
        return RGBColorState.WHITE
    if 30 < hue <= 90:
        return RGBColorState.YELLOW
    if 90 < hue <= 160:
        return RGBColorState.GREEN
    if 150 < hue <= 210:
        return RGBColorState.TURQUOISE
    if 210 < hue <= 270:
        return RGBColorState.BLUE
    if 270 < hue <= 330:
        return RGBColorState.PURPLE
    return RGBColorState.RED


class HomematicipOpticalSignalLight(HomematicipGenericEntity, LightEntity):
    """Representation of a HomematicIP optical signal LED."""

    _attr_color_mode = ColorMode.HS
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_translation_key = "optical_signal_light"

    _effect_to_behaviour: dict[str, OpticalSignalBehaviour] = {
        "on": OpticalSignalBehaviour.ON,
        "blinking": OpticalSignalBehaviour.BLINKING_MIDDLE,
        "flash": OpticalSignalBehaviour.FLASH_MIDDLE,
        "billow": OpticalSignalBehaviour.BILLOW_MIDDLE,
    }
    _behaviour_to_effect: dict[OpticalSignalBehaviour, str] = {
        v: k for k, v in _effect_to_behaviour.items()
    }

    _attr_effect_list = list(_effect_to_behaviour)

    _color_switcher: dict[str, tuple[float, float]] = {
        RGBColorState.WHITE: (0.0, 0.0),
        RGBColorState.RED: (0.0, 100.0),
        RGBColorState.YELLOW: (60.0, 100.0),
        RGBColorState.GREEN: (120.0, 100.0),
        RGBColorState.TURQUOISE: (180.0, 100.0),
        RGBColorState.BLUE: (240.0, 100.0),
        RGBColorState.PURPLE: (300.0, 100.0),
    }

    def __init__(
        self,
        hap: HomematicipHAP,
        device: Device,
        channel_index: int,
        led_number: int,
    ) -> None:
        """Initialize the optical signal light entity."""
        super().__init__(
            hap,
            device,
            post=f"LED {led_number}",
            channel=channel_index,
            is_multi_channel=True,
            channel_real_index=channel_index,
            feature_id="optical_signal_light",
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true if light is on."""
        channel = self.get_channel_or_raise()
        return channel.on is True

    @property
    @override
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        channel = self.get_channel_or_raise()
        return int((channel.dimLevel or 0.0) * 255)

    @property
    @override
    def hs_color(self) -> tuple[float, float]:
        """Return the hue and saturation color value [float, float]."""
        channel = self.get_channel_or_raise()
        simple_rgb_color = channel.simpleRGBColorState
        return self._color_switcher.get(simple_rgb_color, (0.0, 0.0))

    @property
    @override
    def effect(self) -> str | None:
        """Return the current effect."""
        channel = self.get_channel_or_raise()
        return self._behaviour_to_effect.get(channel.opticalSignalBehaviour)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the optical signal light."""
        state_attr = super().extra_state_attributes
        channel = self.get_channel_or_raise()

        if self.is_on:
            state_attr[ATTR_COLOR_NAME] = channel.simpleRGBColorState

        return state_attr

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # Use hs_color from kwargs, if not applicable use current hs_color.
        hs_color = kwargs.get(ATTR_HS_COLOR, self.hs_color)
        simple_rgb_color = _convert_color(hs_color)

        # If no kwargs, use default value.
        brightness = 255
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]

        # Minimum brightness is 10, otherwise the LED is disabled
        brightness = max(10, brightness)
        dim_level = round(brightness / 255.0, 2)

        effect = self.effect
        if ATTR_EFFECT in kwargs:
            effect = kwargs[ATTR_EFFECT]
        elif effect is None:
            effect = "on"

        behaviour = self._effect_to_behaviour.get(effect, OpticalSignalBehaviour.ON)

        await self.get_channel_or_raise().async_set_optical_signal(
            opticalSignalBehaviour=behaviour,
            rgb=simple_rgb_color,
            dimLevel=dim_level,
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        channel = self.get_channel_or_raise()
        simple_rgb_color = channel.simpleRGBColorState

        await channel.async_set_optical_signal(
            opticalSignalBehaviour=OpticalSignalBehaviour.OFF,
            rgb=simple_rgb_color,
            dimLevel=0.0,
        )


class HomematicipCombinationSignallingLight(HomematicipGenericEntity, LightEntity):
    """Representation of the HomematicIP combination signalling device light."""

    _attr_color_mode = ColorMode.HS
    _attr_supported_color_modes = {ColorMode.HS}

    _color_switcher: dict[str, tuple[float, float]] = {
        RGBColorState.WHITE: (0.0, 0.0),
        RGBColorState.RED: (0.0, 100.0),
        RGBColorState.YELLOW: (60.0, 100.0),
        RGBColorState.GREEN: (120.0, 100.0),
        RGBColorState.TURQUOISE: (180.0, 100.0),
        RGBColorState.BLUE: (240.0, 100.0),
        RGBColorState.PURPLE: (300.0, 100.0),
    }

    def __init__(self, hap: HomematicipHAP, device: Device, channel: int) -> None:
        """Initialize the combination signalling light entity."""
        super().__init__(
            hap,
            device,
            channel=channel,
            is_multi_channel=False,
            channel_real_index=channel,
            feature_id="combination_signalling_light",
        )

    @property
    def _func_channel(self) -> NotificationMp3SoundChannel:
        return self.get_channel_or_raise()

    @property
    @override
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._func_channel.on

    @property
    @override
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int((self._func_channel.dimLevel or 0.0) * 255)

    @property
    @override
    def hs_color(self) -> tuple[float, float]:
        """Return the hue and saturation color value [float, float]."""
        simple_rgb_color = self._func_channel.simpleRGBColorState
        return self._color_switcher.get(simple_rgb_color, (0.0, 0.0))

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        hs_color = kwargs.get(ATTR_HS_COLOR, self.hs_color)
        simple_rgb_color = _convert_color(hs_color)

        brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness)

        # Default to full brightness when no kwargs given
        if not kwargs:
            brightness = 255

        # Minimum brightness is 10, otherwise the LED is disabled
        brightness = max(10, brightness)
        dim_level = brightness / 255.0

        await self._func_channel.set_rgb_dim_level_async(
            rgb_color_state=simple_rgb_color.name,
            dim_level=dim_level,
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._func_channel.turn_off_async()
