"""
ZiGate light platform that implements lights.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/ZiGate/
"""
import logging
from functools import reduce
from operator import ior

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP,
    SUPPORT_COLOR, Light)

DOMAIN = 'zigate'
DATA_ZIGATE_DEVICES = 'zigate_devices'
DATA_ZIGATE_ATTRS = 'zigate_attributes'

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the ZiGate sensors."""
    if discovery_info is None:
        return

    z = hass.data[DOMAIN]
    import zigate
    LIGHT_ACTIONS = [zigate.ACTIONS_LEVEL,
                     zigate.ACTIONS_COLOR,
                     zigate.ACTIONS_TEMPERATURE,
                     zigate.ACTIONS_HUE,
                     ]

    def sync_attributes():
        devs = []
        for device in z.devices:
            actions = device.available_actions()
            if not actions:
                continue
            for endpoint, action_type in actions.items():
                if any(i in action_type for i in LIGHT_ACTIONS):
                    key = '{}-{}-{}'.format(device.addr,
                                            'light',
                                            endpoint
                                            )
                    if key not in hass.data[DATA_ZIGATE_ATTRS]:
                        _LOGGER.debug(('Creating light '
                                       'for device '
                                       '{} {}').format(device,
                                                       endpoint))
                        entity = ZiGateLight(device, endpoint)
                        devs.append(entity)
                        hass.data[DATA_ZIGATE_ATTRS][key] = entity

        add_devices(devs)
    sync_attributes()
    zigate.dispatcher.connect(sync_attributes,
                              zigate.ZIGATE_ATTRIBUTE_ADDED, weak=False)


class ZiGateLight(Light):
    """Representation of a ZiGate light."""

    def __init__(self, device, endpoint):
        """Initialize the light."""
        self._device = device
        self._endpoint = endpoint
        self._name = 'zigate_{}_{}_{}'.format(device.addr,
                                              'light',
                                              endpoint)
        self._unique_id = '{}-{}-{}'.format(device.addr,
                                            'light',
                                            endpoint)
        import zigate
        supported_features = set()
        for action_type in device.available_actions(endpoint)[endpoint]:
            if action_type == zigate.ACTIONS_LEVEL:
                supported_features.add(SUPPORT_BRIGHTNESS)
            elif action_type == zigate.ACTIONS_COLOR:
                supported_features.add(SUPPORT_COLOR)
            elif action_type == zigate.ACTIONS_TEMPERATURE:
                supported_features.add(SUPPORT_COLOR_TEMP)
            elif action_type == zigate.ACTIONS_HUE:
                supported_features.add(SUPPORT_COLOR)
        self._supported_features = reduce(ior, supported_features)

    @property
    def should_poll(self) -> bool:
        """No polling needed for a ZiGate light."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the light if any."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID for light."""
        return self._unique_id

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        a = self._device.get_attribute(self._endpoint, 8, 0)
        if a:
            return int(a.get('value', 0)*255/100)
        return 0

#     @property
#     def hs_color(self) -> tuple:
#         """Return the hs color value."""
#         return self._hs_color
#
#     @property
#     def color_temp(self) -> int:
#         """Return the CT color temperature."""
#         return self._ct
#
#     @property
#     def white_value(self) -> int:
#         """Return the white value of this light between 0..255."""
#         return self._white
#
#     @property
#     def effect_list(self) -> list:
#         """Return the list of supported effects."""
#         return self._effect_list
#
#     @property
#     def effect(self) -> str:
#         """Return the current effect."""
#         return self._effect

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        a = self._device.get_attribute(self._endpoint, 6, 0)
        if a:
            return a.get('value', False)
        return False

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            brightness = int((brightness / 255) * 100)
            self.hass.data[DOMAIN].action_move_level_onoff(self._device.addr,
                                                           self._endpoint,
                                                           1,
                                                           brightness
                                                           )
        else:
            self.hass.data[DOMAIN].action_onoff(self._device.addr,
                                                self._endpoint,
                                                1)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.hass.data[DOMAIN].action_onoff(self._device.addr,
                                            self._endpoint,
                                            0)

    def toggle(self, **kwargs):
        """Toggle the device"""
        self.hass.data[DOMAIN].action_onoff(self._device.addr,
                                            self._endpoint,
                                            2)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            'addr': self._device.addr,
            'endpoint': self._endpoint,
        }
