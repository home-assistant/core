"""
Lights on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/light.zha/
"""
import logging

from homeassistant.components import light
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.util.color as color_util
from .const import (
    DATA_ZHA, DATA_ZHA_DISPATCHERS, ZHA_DISCOVERY_NEW, LISTENER_COLOR,
    LISTENER_ON_OFF, LISTENER_LEVEL, SIGNAL_ATTR_UPDATED, SIGNAL_SET_LEVEL
    )
from .entity import ZhaEntity


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha']

DEFAULT_DURATION = 0.5

CAPABILITIES_COLOR_XY = 0x08
CAPABILITIES_COLOR_TEMP = 0x10

UNSUPPORTED_ATTRIBUTE = 0x86


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Old way of setting up Zigbee Home Automation lights."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation light from config entry."""
    async def async_discover(discovery_info):
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    [discovery_info])

    unsub = async_dispatcher_connect(
        hass, ZHA_DISCOVERY_NEW.format(light.DOMAIN), async_discover)
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)

    lights = hass.data.get(DATA_ZHA, {}).get(light.DOMAIN)
    if lights is not None:
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    lights.values())
        del hass.data[DATA_ZHA][light.DOMAIN]


async def _async_setup_entities(hass, config_entry, async_add_entities,
                                discovery_infos):
    """Set up the ZHA lights."""
    entities = []
    for discovery_info in discovery_infos:
        zha_light = Light(**discovery_info)
        entities.append(zha_light)

    async_add_entities(entities, update_before_add=True)


class Light(ZhaEntity, light.Light):
    """Representation of a ZHA or ZLL light."""

    _domain = light.DOMAIN

    def __init__(self, unique_id, zha_device, listeners, **kwargs):
        """Initialize the ZHA light."""
        super().__init__(unique_id, zha_device, listeners, **kwargs)
        self._supported_features = 0
        self._color_temp = None
        self._hs_color = None
        self._brightness = None
        self._on_off_listener = self.cluster_listeners.get(LISTENER_ON_OFF)
        self._level_listener = self.cluster_listeners.get(LISTENER_LEVEL)
        self._color_listener = self.cluster_listeners.get(LISTENER_COLOR)

        if self._level_listener:
            self._supported_features |= light.SUPPORT_BRIGHTNESS
            self._supported_features |= light.SUPPORT_TRANSITION
            self._brightness = 0

        if self._color_listener:
            color_capabilities = self._color_listener.get_color_capabilities()
            if color_capabilities & CAPABILITIES_COLOR_TEMP:
                self._supported_features |= light.SUPPORT_COLOR_TEMP

            if color_capabilities & CAPABILITIES_COLOR_XY:
                self._supported_features |= light.SUPPORT_COLOR
                self._hs_color = (0, 0)

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        if self._state is None:
            return False
        return self._state

    @property
    def brightness(self):
        """Return the brightness of this light."""
        return self._brightness

    @property
    def device_state_attributes(self):
        """Return state attributes."""
        return self.state_attributes

    def set_level(self, value):
        """Set the brightness of this light between 0..255."""
        value = max(0, min(255, value))
        self._brightness = value
        self.async_schedule_update_ha_state()

    @property
    def hs_color(self):
        """Return the hs color value [int, int]."""
        return self._hs_color

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        return self._color_temp

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    def async_set_state(self, state):
        """Set the state."""
        self._state = bool(state)
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        await self.async_accept_signal(
            self._on_off_listener, SIGNAL_ATTR_UPDATED, self.async_set_state)
        if self._level_listener:
            await self.async_accept_signal(
                self._level_listener, SIGNAL_SET_LEVEL, self.set_level)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        duration = kwargs.get(light.ATTR_TRANSITION, DEFAULT_DURATION)
        duration = duration * 10  # tenths of s

        if light.ATTR_COLOR_TEMP in kwargs and \
                self.supported_features & light.SUPPORT_COLOR_TEMP:
            temperature = kwargs[light.ATTR_COLOR_TEMP]
            success = await self._color_listener.move_to_color_temp(
                temperature, duration)
            if not success:
                return
            self._color_temp = temperature

        if light.ATTR_HS_COLOR in kwargs and \
                self.supported_features & light.SUPPORT_COLOR:
            hs_color = kwargs[light.ATTR_HS_COLOR]
            xy_color = color_util.color_hs_to_xy(*hs_color)
            success = await self._color_listener.move_to_color(
                int(xy_color[0] * 65535),
                int(xy_color[1] * 65535),
                duration,
            )
            if not success:
                return
            self._hs_color = hs_color

        if self._brightness is not None:
            brightness = kwargs.get(
                light.ATTR_BRIGHTNESS, self._brightness or 255)
            success = await self._level_listener.move_to_level_with_on_off(
                brightness,
                duration
            )
            if not success:
                return
            self._state = True
            self._brightness = brightness
            self.async_schedule_update_ha_state()
            return

        success = await self._on_off_listener.on()
        if not success:
            return

        self._state = True
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        duration = kwargs.get(light.ATTR_TRANSITION)
        supports_level = self.supported_features & light.SUPPORT_BRIGHTNESS
        success = None
        if duration and supports_level:
            success = await self._level_listener.move_to_level_with_on_off(
                0,
                duration*10
            )
        else:
            success = await self._on_off_listener.off()
        _LOGGER.debug("%s was turned off: %s", self.entity_id, success)
        if not success:
            return
        self._state = False
        self.async_schedule_update_ha_state()
