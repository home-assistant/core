"""Support for HomematicIP Cloud lights."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_NAME, ATTR_HS_COLOR, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR, Light)

from . import DOMAIN as HMIPC_DOMAIN, HMIPC_HAPID, HomematicipGenericDevice

DEPENDENCIES = ['homematicip_cloud']

_LOGGER = logging.getLogger(__name__)

ATTR_ENERGY_COUNTER = 'energy_counter_kwh'
ATTR_POWER_CONSUMPTION = 'power_consumption'
ATTR_PROFILE_MODE = 'profile_mode'


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

    def __init__(self, home, device, channel_index):
        """Initialize the dimmer light device."""
        self._channel_index = channel_index
        if self._channel_index == 2:
            super().__init__(home, device, 'Top')
        else:
            super().__init__(home, device, 'Bottom')

        from homematicip.base.enums import RGBColorState
        self._color_switcher = {
            RGBColorState.WHITE: [0.0, 0.0],
            RGBColorState.RED: [0.0, 100.0],
            RGBColorState.YELLOW: [60.0, 100.0],
            RGBColorState.GREEN: [120.0, 100.0],
            RGBColorState.TURQUOISE: [180.0, 100.0],
            RGBColorState.BLUE: [240.0, 100.0],
            RGBColorState.PURPLE: [300.0, 100.0]
        }

    @property
    def _channel(self):
        return self._device.functionalChannels[self._channel_index]

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._channel.dimLevel > 0.0

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return int(self._channel.dimLevel * 255)

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        simple_rgb_color = self._channel.simpleRGBColorState
        return self._color_switcher.get(simple_rgb_color, [0.0, 0.0])

    @property
    def device_state_attributes(self):
        """Return the state attributes of the generic device."""
        attr = super().device_state_attributes
        if self.is_on:
            attr.update({
                ATTR_COLOR_NAME:
                    self._channel.simpleRGBColorState
            })
        return attr

    @property
    def name(self):
        """Return the name of the generic device."""
        return "{} {}".format(super().name, 'Notification')

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "{}_{}_{}".format(self.__class__.__name__,
                                 self.post,
                                 self._device.id)

    async def async_turn_on(self, **kwargs):
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

        await self._device.set_rgb_dim_level(
            self._channel_index,
            simple_rgb_color,
            dim_level)

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        simple_rgb_color = self._channel.simpleRGBColorState
        await self._device.set_rgb_dim_level(
            self._channel_index,
            simple_rgb_color, 0.0)


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
