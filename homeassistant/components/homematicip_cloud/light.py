"""
Support for HomematicIP Cloud lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.homematicip_cloud/
"""
import logging

from homeassistant.components.homematicip_cloud import (
    DOMAIN as HMIPC_DOMAIN, HMIPC_HAPID, HomematicipGenericDevice)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_HS_COLOR, SUPPORT_BRIGHTNESS, SUPPORT_COLOR, Light)
from homeassistant.const import STATE_OFF, STATE_ON

DEPENDENCIES = ['homematicip_cloud']

_LOGGER = logging.getLogger(__name__)

ATTR_ENERGY_COUNTER = 'energy_counter_kwh'
ATTR_POWER_CONSUMPTION = 'power_consumption'
ATTR_PROFILE_MODE = 'profile_mode'
ATTR_SIMPLE_RGB_COLOR = 'simple_rgb_color'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up HomematicIP Cloud lights."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the HomematicIP Cloud lights from a config entry."""
    from homematicip.aio.device import AsyncBrandSwitchMeasuring, AsyncDimmer,\
        AsyncPluggableDimmer, AsyncBrandDimmer, AsyncFullFlushDimmer,\
        AsyncBrandSwitchNotificationLight

    home = hass.data[HMIPC_DOMAIN][config_entry.data[HMIPC_HAPID]].home
    devices = []
    for device in home.devices:
        if isinstance(device, AsyncBrandSwitchMeasuring):
            devices.append(HomematicipLightMeasuring(home, device))
        elif isinstance(device, AsyncBrandSwitchNotificationLight):
            devices.append(HomematicipLight(home, device))
            devices.append(HomematicipNotificationLight(
                home, device, device.topLightChannelIndex))
            devices.append(HomematicipNotificationLight(
                home, device, device.bottomLightChannelIndex))
        elif isinstance(device,
                        (AsyncDimmer, AsyncPluggableDimmer,
                         AsyncBrandDimmer, AsyncFullFlushDimmer)):
            devices.append(HomematicipDimmer(home, device))

    if devices:
        async_add_entities(devices)


class HomematicipLight(HomematicipGenericDevice, Light):
    """Representation of a HomematicIP Cloud light device."""

    def __init__(self, home, device):
        """Initialize the light device."""
        super().__init__(home, device)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.on

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._device.turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._device.turn_off()


class HomematicipLightMeasuring(HomematicipLight):
    """Representation of a HomematicIP Cloud measuring light device."""

    @property
    def device_state_attributes(self):
        """Return the state attributes of the generic device."""
        attr = super().device_state_attributes
        if self._device.currentPowerConsumption > 0.05:
            attr.update({
                ATTR_POWER_CONSUMPTION:
                    round(self._device.currentPowerConsumption, 2)
            })
        attr.update({
            ATTR_ENERGY_COUNTER: round(self._device.energyCounter, 2)
        })
        return attr


class HomematicipDimmer(HomematicipGenericDevice, Light):
    """Representation of HomematicIP Cloud dimmer light device."""

    def __init__(self, home, device):
        """Initialize the dimmer light device."""
        super().__init__(home, device)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.dimLevel != 0

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return int(self._device.dimLevel*255)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            await self._device.set_dim_level(kwargs[ATTR_BRIGHTNESS]/255.0)
        else:
            await self._device.set_dim_level(1)

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._device.set_dim_level(0)


class HomematicipNotificationLight(HomematicipGenericDevice, Light):
    """Representation of HomematicIP Cloud dimmer light device."""

    from homematicip.base.enums import RGBColorState

    channel_index = None

    channel_name = None

    # Dictionary to translate between RGBColorState and hs_color
    __color_switcher = {
        RGBColorState.WHITE: [0.0, 0.0],
        RGBColorState.RED: [0.0, 100.0],
        RGBColorState.YELLOW: [60.0, 100.0],
        RGBColorState.GREEN: [120.0, 100.0],
        RGBColorState.TURQUOISE: [180.0, 100.0],
        RGBColorState.BLUE: [240.0, 100.0],
        RGBColorState.PURPLE: [300.0, 100.0]
    }

    def __init__(self, home, device, channel_Index: int):
        """Initialize the dimmer light device."""
        super().__init__(home, device)
        self.channel_index = channel_Index
        if self.channel_index == 2:
            self.channel_name = 'Top'
        else:
            self.channel_name = 'Buttom'

    def _channel(self):
        return self._device.functionalChannels[self.channel_index]

    @property
    def is_on(self):
        """Return true if device is on."""
        from homematicip.base.enums import RGBColorState

        return self._channel().dimLevel > 0.0 and not \
            self._channel().simpleRGBColorState == RGBColorState.BLACK

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return int(self._channel().dimLevel * 255)

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        simple_rgb_color = self._channel().simpleRGBColorState
        return self.__color_switcher.get(simple_rgb_color, [0.0, 0.0])

    @property
    def device_state_attributes(self):
        """Return the state attributes of the generic device."""
        attr = super().device_state_attributes
        if self.is_on:
            attr.update({
                ATTR_BRIGHTNESS:
                    round(self.brightness, 2)
            })
            attr.update({
                ATTR_SIMPLE_RGB_COLOR:
                    self._channel().simpleRGBColorState
            })
        return attr

    @property
    def name(self):
        """Return the name of the generic device."""
        return "{} {} {}".format(super().name,
                                 'Notification',
                                 self.channel_name)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR

    @property
    def state(self) -> str:
        """Return the state."""
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "{}_{}_{}".format(self.__class__.__name__,
                                 self._device.id,
                                 self.channel_name)

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        from homematicip.base.enums import RGBColorState

        # Use hs_color from kwargs,
        # if not applicable use current hs_color.
        hs_color = kwargs.get(ATTR_HS_COLOR, None)
        if hs_color is None:
            hs_color = self.hs_color
        simple_rgb_color = _convert_color(hs_color)

        # Use brightness from kwargs,
        # if not applicable use current brightness.
        brightness = kwargs.get(ATTR_BRIGHTNESS, None)
        if brightness is None:
            brightness = self.brightness

        # Minimum brightness is 10, otherwise the led is disabled
        if brightness < 10:
            brightness = 10
        dim_level = brightness / 255.0

        # If no kwargs, use default value.
        if kwargs.__len__() == 0:
            dim_level = 1.0
            simple_rgb_color = RGBColorState.WHITE

        await self._device.set_rgb_dim_level(
            self.channel_index,
            simple_rgb_color,
            dim_level)

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        from homematicip.base.enums import RGBColorState
        await self._device.set_rgb_dim_level(
            self.channel_index,
            RGBColorState.BLACK, 0.0)


def _convert_color(color):
    """
    Convert the given color to the reduced RGBColorState color.

    RGBColorStat contains only 8 colors including white and black,
    so a conversion is required.
    """
    from homematicip.base.enums import RGBColorState

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
