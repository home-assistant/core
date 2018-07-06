"""
ZiGate platform.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/ZiGate/
"""
import logging
from homeassistant.components.switch import SwitchDevice

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

    def sync_attributes():
        devs = []
        for device in z.devices:
            actions = device.available_actions()
            if not actions:
                continue
            for endpoint, action_type in actions.items():
                if [zigate.ACTIONS_ONOFF] == action_type:
                    key = '{}-{}-{}'.format(device.addr,
                                            'switch',
                                            endpoint
                                            )
                    if key not in hass.data[DATA_ZIGATE_ATTRS]:
                        _LOGGER.debug(('Creating switch '
                                       'for device '
                                       '{} {}').format(device,
                                                       endpoint))
                        entity = ZiGateSwitch(device, endpoint)
                        devs.append(entity)
                        hass.data[DATA_ZIGATE_ATTRS][key] = entity

        add_devices(devs)
    sync_attributes()
    zigate.dispatcher.connect(sync_attributes,
                              zigate.ZIGATE_ATTRIBUTE_ADDED, weak=False)


class ZiGateSwitch(SwitchDevice):
    """Representation of a ZiGate switch."""

    def __init__(self, device, endpoint):
        """Initialize the ZiGate switch."""
        self._device = device
        self._endpoint = endpoint
        self._name = 'zigate_{}_{}_{}'.format(device.addr,
                                              'switch',
                                              endpoint)
        self._unique_id = '{}-{}-{}'.format(device.addr,
                                            'switch',
                                            endpoint)
        self.registry_name = '{} {}'.format(device, endpoint)

    @property
    def unique_id(self)->str:
        return self._unique_id

    @property
    def should_poll(self):
        """No polling needed for a ZiGate switch."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

#     @property
#     def current_power_w(self):
#         """Return the current power usage in W."""
#         if self._state:
#             return 100
#
#     @property
#     def today_energy_kwh(self):
#         """Return the today total energy usage in kWh."""
#         return 15

    @property
    def is_on(self):
        """Return true if switch is on."""
        a = self._device.get_attribute(self._endpoint, 6, 0)
        if a:
            return a.get('value', False)
        return False

    def turn_on(self, **kwargs):
        """Turn the switch on."""
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
