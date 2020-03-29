"""Support for HomematicIP Cloud lights."""
import logging
from typing import Any, Dict

from homematicip.aio.device import (
    AsyncBrandDimmer,
    AsyncBrandSwitchMeasuring,
    AsyncBrandSwitchNotificationLight,
    AsyncDimmer,
    AsyncFullFlushDimmer,
    AsyncPluggableDimmer,
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
    Light,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import DOMAIN as HMIPC_DOMAIN, HomematicipGenericDevice
from .hap import HomematicipHAP

_LOGGER = logging.getLogger(__name__)

ATTR_TODAY_ENERGY_KWH = "today_energy_kwh"
ATTR_CURRENT_POWER_W = "current_power_w"


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the HomematicIP Cloud lights from a config entry."""
    hap = hass.data[HMIPC_DOMAIN][config_entry.unique_id]
    entities = []
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
        elif isinstance(
            device,
            (AsyncDimmer, AsyncPluggableDimmer, AsyncBrandDimmer, AsyncFullFlushDimmer),
        ):
            entities.append(HomematicipDimmer(hap, device))

    if entities:
        async_add_entities(entities)


class HomematicipLight(HomematicipGenericDevice, Light):
    """Representation of a HomematicIP Cloud light device."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the light device."""
        super().__init__(hap, device)

    @property
    def name(self) -> str:
        """Return the name of the multi switch channel."""
        label = self._get_label_by_channel(1)
        if label:
            return label
        return super().name

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device.on

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the device on."""
        await self._device.turn_on()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the device off."""
        await self._device.turn_off()


class HomematicipLightMeasuring(HomematicipLight):
    """Representation of a HomematicIP Cloud measuring light device."""

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes of the generic device."""
        state_attr = super().device_state_attributes

        current_power_w = self._device.currentPowerConsumption
        if current_power_w > 0.05:
            state_attr[ATTR_CURRENT_POWER_W] = round(current_power_w, 2)

        state_attr[ATTR_TODAY_ENERGY_KWH] = round(self._device.energyCounter, 2)

        return state_attr


class HomematicipDimmer(HomematicipGenericDevice, Light):
    """Representation of HomematicIP Cloud dimmer light device."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the dimmer light device."""
        super().__init__(hap, device)

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device.dimLevel is not None and self._device.dimLevel > 0.0

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int((self._device.dimLevel or 0.0) * 255)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            await self._device.set_dim_level(kwargs[ATTR_BRIGHTNESS] / 255.0)
        else:
            await self._device.set_dim_level(1)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        await self._device.set_dim_level(0)


class HomematicipNotificationLight(HomematicipGenericDevice, Light):
    """Representation of HomematicIP Cloud dimmer light device."""

    def __init__(self, hap: HomematicipHAP, device, channel: int) -> None:
        """Initialize the dimmer light device."""
        self.channel = channel
        if self.channel == 2:
            super().__init__(hap, device, "Top")
        else:
            super().__init__(hap, device, "Bottom")

        self._color_switcher = {
            RGBColorState.WHITE: [0.0, 0.0],
            RGBColorState.RED: [0.0, 100.0],
            RGBColorState.YELLOW: [60.0, 100.0],
            RGBColorState.GREEN: [120.0, 100.0],
            RGBColorState.TURQUOISE: [180.0, 100.0],
            RGBColorState.BLUE: [240.0, 100.0],
            RGBColorState.PURPLE: [300.0, 100.0],
        }

    @property
    def _func_channel(self) -> NotificationLightChannel:
        return self._device.functionalChannels[self.channel]

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return (
            self._func_channel.dimLevel is not None
            and self._func_channel.dimLevel > 0.0
        )

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int((self._func_channel.dimLevel or 0.0) * 255)

    @property
    def hs_color(self) -> tuple:
        """Return the hue and saturation color value [float, float]."""
        simple_rgb_color = self._func_channel.simpleRGBColorState
        return self._color_switcher.get(simple_rgb_color, [0.0, 0.0])

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes of the generic device."""
        state_attr = super().device_state_attributes

        if self.is_on:
            state_attr[ATTR_COLOR_NAME] = self._func_channel.simpleRGBColorState

        return state_attr

    @property
    def name(self) -> str:
        """Return the name of the generic device."""
        label = self._get_label_by_channel(self.channel)
        if label:
            return label
        return f"{super().name} Notification"

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_TRANSITION

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.__class__.__name__}_{self.post}_{self._device.id}"

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
            channelIndex=self.channel,
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
            channelIndex=self.channel,
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
