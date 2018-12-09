"""
Lights on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/light.zha/
"""
import logging

from homeassistant.components import light
from homeassistant.components.zha import helpers
from homeassistant.components.zha.const import (
    DATA_ZHA, DATA_ZHA_DISPATCHERS, ZHA_DISCOVERY_NEW)
from homeassistant.components.zha.entities import ZhaEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.util.color as color_util

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
        endpoint = discovery_info['endpoint']
        if hasattr(endpoint, 'light_color'):
            caps = await helpers.safe_read(
                endpoint.light_color, ['color_capabilities'])
            discovery_info['color_capabilities'] = caps.get(
                'color_capabilities')
            if discovery_info['color_capabilities'] is None:
                # ZCL Version 4 devices don't support the color_capabilities
                # attribute. In this version XY support is mandatory, but we
                # need to probe to determine if the device supports color
                # temperature.
                discovery_info['color_capabilities'] = \
                    CAPABILITIES_COLOR_XY
                result = await helpers.safe_read(
                    endpoint.light_color, ['color_temperature'])
                if (result.get('color_temperature') is not
                        UNSUPPORTED_ATTRIBUTE):
                    discovery_info['color_capabilities'] |= \
                        CAPABILITIES_COLOR_TEMP
        entities.append(Light(**discovery_info))

    async_add_entities(entities, update_before_add=True)


class Light(ZhaEntity, light.Light):
    """Representation of a ZHA or ZLL light."""

    _domain = light.DOMAIN

    def __init__(self, **kwargs):
        """Initialize the ZHA light."""
        super().__init__(**kwargs)
        self._supported_features = 0
        self._color_temp = None
        self._hs_color = None
        self._brightness = None

        import zigpy.zcl.clusters as zcl_clusters
        if zcl_clusters.general.LevelControl.cluster_id in self._in_clusters:
            self._supported_features |= light.SUPPORT_BRIGHTNESS
            self._supported_features |= light.SUPPORT_TRANSITION
            self._brightness = 0
        if zcl_clusters.lighting.Color.cluster_id in self._in_clusters:
            color_capabilities = kwargs['color_capabilities']
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
        return bool(self._state)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        from zigpy.exceptions import DeliveryError

        duration = kwargs.get(light.ATTR_TRANSITION, DEFAULT_DURATION)
        duration = duration * 10  # tenths of s
        if light.ATTR_COLOR_TEMP in kwargs:
            temperature = kwargs[light.ATTR_COLOR_TEMP]
            try:
                res = await self._endpoint.light_color.move_to_color_temp(
                    temperature, duration)
                _LOGGER.debug("%s: moved to %i color temp: %s",
                              self.entity_id, temperature, res)
            except DeliveryError as ex:
                _LOGGER.error("%s: Couldn't change color temp: %s",
                              self.entity_id, ex)
                return
            self._color_temp = temperature

        if light.ATTR_HS_COLOR in kwargs:
            self._hs_color = kwargs[light.ATTR_HS_COLOR]
            xy_color = color_util.color_hs_to_xy(*self._hs_color)
            try:
                res = await self._endpoint.light_color.move_to_color(
                    int(xy_color[0] * 65535),
                    int(xy_color[1] * 65535),
                    duration,
                )
                _LOGGER.debug("%s: moved XY color to (%1.2f, %1.2f): %s",
                              self.entity_id, xy_color[0], xy_color[1], res)
            except DeliveryError as ex:
                _LOGGER.error("%s: Couldn't change color temp: %s",
                              self.entity_id, ex)
                return

        if self._brightness is not None:
            brightness = kwargs.get(
                light.ATTR_BRIGHTNESS, self._brightness or 255)
            self._brightness = brightness
            # Move to level with on/off:
            try:
                res = await self._endpoint.level.move_to_level_with_on_off(
                    brightness,
                    duration
                )
                _LOGGER.debug("%s: moved to %i level with on/off: %s",
                              self.entity_id, brightness, res)
            except DeliveryError as ex:
                _LOGGER.error("%s: Couldn't change brightness level: %s",
                              self.entity_id, ex)
                return
            self._state = 1
            self.async_schedule_update_ha_state()
            return

        try:
            res = await self._endpoint.on_off.on()
            _LOGGER.debug("%s was turned on: %s", self.entity_id, res)
        except DeliveryError as ex:
            _LOGGER.error("%s: Unable to turn the light on: %s",
                          self.entity_id, ex)
            return

        self._state = 1
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        from zigpy.exceptions import DeliveryError
        try:
            res = await self._endpoint.on_off.off()
            _LOGGER.debug("%s was turned off: %s", self.entity_id, res)
        except DeliveryError as ex:
            _LOGGER.error("%s: Unable to turn the light off: %s",
                          self.entity_id, ex)
            return

        self._state = 0
        self.async_schedule_update_ha_state()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

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

    async def async_update(self):
        """Retrieve latest state."""
        result = await helpers.safe_read(self._endpoint.on_off, ['on_off'],
                                         allow_cache=False,
                                         only_cache=(not self._initialized))
        self._state = result.get('on_off', self._state)

        if self._supported_features & light.SUPPORT_BRIGHTNESS:
            result = await helpers.safe_read(self._endpoint.level,
                                             ['current_level'],
                                             allow_cache=False,
                                             only_cache=(
                                                 not self._initialized
                                             ))
            self._brightness = result.get('current_level', self._brightness)

        if self._supported_features & light.SUPPORT_COLOR_TEMP:
            result = await helpers.safe_read(self._endpoint.light_color,
                                             ['color_temperature'],
                                             allow_cache=False,
                                             only_cache=(
                                                 not self._initialized
                                             ))
            self._color_temp = result.get('color_temperature',
                                          self._color_temp)

        if self._supported_features & light.SUPPORT_COLOR:
            result = await helpers.safe_read(self._endpoint.light_color,
                                             ['current_x', 'current_y'],
                                             allow_cache=False,
                                             only_cache=(
                                                 not self._initialized
                                             ))
            if 'current_x' in result and 'current_y' in result:
                xy_color = (round(result['current_x']/65535, 3),
                            round(result['current_y']/65535, 3))
                self._hs_color = color_util.color_xy_to_hs(*xy_color)

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False
