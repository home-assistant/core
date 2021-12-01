"""Support for HomematicIP Cloud lights."""
from __future__ import annotations

from typing import Any

from homematicip.aio.device import (
    AsyncBrandDimmer,
    AsyncBrandSwitchMeasuring,
    AsyncBrandSwitchNotificationLight,
    AsyncDimmer,
    AsyncFullFlushDimmer,
    AsyncPluggableDimmer,
    AsyncWiredDimmer3,
)
from homematicip.base.enums import RGBColorState
from homematicip.base.functionalChannels import NotificationLightChannel

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_NAME,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DOMAIN as HMIPC_DOMAIN, HomematicipGenericEntity
from .hap import HomematicipHAP

ATTR_TODAY_ENERGY_KWH = "today_energy_kwh"
ATTR_CURRENT_POWER_W = "current_power_w"


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the HomematicIP Cloud lights from a config entry."""
    hap = hass.data[HMIPC_DOMAIN][config_entry.unique_id]
    entities: list[HomematicipGenericEntity] = []
    for device in hap.home.devices:
        if isinstance(device, AsyncBrandSwitchMeasuring):
            entities.append(HomematicipLightMeasuring(hap, device))
        elif isinstance(device, AsyncBrandSwitchNotificationLight):
            entities.append(HomematicipLight(hap, device))
            entities.append(
                HomematicipNotificationLight(hap, device, device.topLightChannelIndex)
            )
            entities.append(
                HomematicipNotificationLight(
                    hap, device, device.bottomLightChannelIndex
                )
            )
        elif isinstance(device, AsyncWiredDimmer3):
            for channel in range(1, 4):
                entities.append(HomematicipMultiDimmer(hap, device, channel=channel))
        elif isinstance(
            device,
            (AsyncDimmer, AsyncPluggableDimmer, AsyncBrandDimmer, AsyncFullFlushDimmer),
        ):
            entities.append(HomematicipDimmer(hap, device))

    if entities:
        async_add_entities(entities)


class HomematicipLight(HomematicipGenericEntity, LightEntity):
    """Representation of the HomematicIP light."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the light entity."""
        super().__init__(hap, device)

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._device.on

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the light on."""
        await self._device.turn_on()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        await self._device.turn_off()


class HomematicipLightMeasuring(HomematicipLight):
    """Representation of the HomematicIP measuring light."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the light."""
        state_attr = super().extra_state_attributes

        current_power_w = self._device.currentPowerConsumption
        if current_power_w > 0.05:
            state_attr[ATTR_CURRENT_POWER_W] = round(current_power_w, 2)

        state_attr[ATTR_TODAY_ENERGY_KWH] = round(self._device.energyCounter, 2)

        return state_attr


class HomematicipMultiDimmer(HomematicipGenericEntity, LightEntity):
    """Representation of HomematicIP Cloud dimmer."""

    def __init__(
        self,
        hap: HomematicipHAP,
        device,
        channel=1,
        is_multi_channel=True,
    ) -> None:
        """Initialize the dimmer light entity."""
        super().__init__(
            hap, device, channel=channel, is_multi_channel=is_multi_channel
        )

    @property
    def is_on(self) -> bool:
        """Return true if dimmer is on."""
        func_channel = self._device.functionalChannels[self._channel]
        return func_channel.dimLevel is not None and func_channel.dimLevel > 0.0

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int(
            (self._device.functionalChannels[self._channel].dimLevel or 0.0) * 255
        )

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the dimmer on."""
        if ATTR_BRIGHTNESS in kwargs:
            await self._device.set_dim_level(
                kwargs[ATTR_BRIGHTNESS] / 255.0, self._channel
            )
        else:
            await self._device.set_dim_level(1, self._channel)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the dimmer off."""
        await self._device.set_dim_level(0, self._channel)


class HomematicipDimmer(HomematicipMultiDimmer, LightEntity):
    """Representation of HomematicIP Cloud dimmer."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the dimmer light entity."""
        super().__init__(hap, device, is_multi_channel=False)


class HomematicipNotificationLight(HomematicipGenericEntity, LightEntity):
    """Representation of HomematicIP Cloud notification light."""

    def __init__(self, hap: HomematicipHAP, device, channel: int) -> None:
        """Initialize the notification light entity."""
        if channel == 2:
            super().__init__(
                hap, device, post="Top", channel=channel, is_multi_channel=True
            )
        else:
            super().__init__(
                hap, device, post="Bottom", channel=channel, is_multi_channel=True
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
        return self._device.functionalChannels[self._channel]

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return (
            self._func_channel.dimLevel is not None
            and self._func_channel.dimLevel > 0.0
        )

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int((self._func_channel.dimLevel or 0.0) * 255)

    @property
    def hs_color(self) -> tuple[float, float]:
        """Return the hue and saturation color value [float, float]."""
        simple_rgb_color = self._func_channel.simpleRGBColorState
        return self._color_switcher.get(simple_rgb_color, (0.0, 0.0))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the notification light sensor."""
        state_attr = super().extra_state_attributes

        if self.is_on:
            state_attr[ATTR_COLOR_NAME] = self._func_channel.simpleRGBColorState

        return state_attr

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_TRANSITION

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.__class__.__name__}_{self._post}_{self._device.id}"

    async def async_turn_on(self, **kwargs) -> None:
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

        await self._device.set_rgb_dim_level_with_time(
            channelIndex=self._channel,
            rgb=simple_rgb_color,
            dimLevel=dim_level,
            onTime=0,
            rampTime=transition,
        )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        simple_rgb_color = self._func_channel.simpleRGBColorState
        transition = kwargs.get(ATTR_TRANSITION, 0.5)

        await self._device.set_rgb_dim_level_with_time(
            channelIndex=self._channel,
            rgb=simple_rgb_color,
            dimLevel=0.0,
            onTime=0,
            rampTime=transition,
        )


def _convert_color(color: tuple) -> RGBColorState:
    """
    Convert the given color to the reduced RGBColorState color.

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
