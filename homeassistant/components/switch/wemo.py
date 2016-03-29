"""
Support for WeMo switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.wemo/
"""
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    STATE_OFF, STATE_ON, STATE_STANDBY, STATE_UNKNOWN)
from homeassistant.loader import get_component

DEPENDENCIES = ['wemo']

_LOGGER = logging.getLogger(__name__)

ATTR_SENSOR_STATE = "sensor_state"
ATTR_SWITCH_MODE = "switch_mode"
ATTR_CURRENT_STATE_DETAIL = 'state_detail'

MAKER_SWITCH_MOMENTARY = "momentary"
MAKER_SWITCH_TOGGLE = "toggle"

MAKER_SWITCH_MOMENTARY = "momentary"
MAKER_SWITCH_TOGGLE = "toggle"

WEMO_ON = 1
WEMO_OFF = 0
WEMO_STANDBY = 8


# pylint: disable=unused-argument, too-many-function-args
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup discovered WeMo switches."""
    import pywemo.discovery as discovery

    if discovery_info is not None:
        location = discovery_info[2]
        mac = discovery_info[3]
        device = discovery.device_from_description(location, mac)

        if device:
            add_devices_callback([WemoSwitch(device)])


class WemoSwitch(SwitchDevice):
    """Representation of a WeMo switch."""

    def __init__(self, device):
        """Initialize the WeMo switch."""
        self.wemo = device
        self.insight_params = None
        self.maker_params = None
        self._state = None

        wemo = get_component('wemo')
        wemo.SUBSCRIPTION_REGISTRY.register(self.wemo)
        wemo.SUBSCRIPTION_REGISTRY.on(self.wemo, None, self._update_callback)

    def _update_callback(self, _device, _params):
        """Called by the Wemo device callback to update state."""
        _LOGGER.info(
            'Subscription update for  %s',
            _device)
        if not hasattr(self, 'hass'):
            self.update()
            return
        self.update_ha_state(True)

    @property
    def should_poll(self):
        """No polling needed with subscriptions."""
        return False

    @property
    def unique_id(self):
        """Return the ID of this WeMo switch."""
        return "{}.{}".format(self.__class__, self.wemo.serialnumber)

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self.wemo.name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        if self.maker_params:
            # Is the maker sensor on or off.
            if self.maker_params['hassensor']:
                # Note a state of 1 matches the WeMo app 'not triggered'!
                if self.maker_params['sensorstate']:
                    attr[ATTR_SENSOR_STATE] = STATE_OFF
                else:
                    attr[ATTR_SENSOR_STATE] = STATE_ON

            # Is the maker switch configured as toggle(0) or momentary (1).
            if self.maker_params['switchmode']:
                attr[ATTR_SWITCH_MODE] = MAKER_SWITCH_MOMENTARY
            else:
                attr[ATTR_SWITCH_MODE] = MAKER_SWITCH_TOGGLE

        if self.insight_params:
            attr[ATTR_CURRENT_STATE_DETAIL] = self.detail_state

        return attr

    @property
    def current_power_mwh(self):
        """Current power usage in mWh."""
        if self.insight_params:
            return self.insight_params['currentpower']

    @property
    def today_power_mw(self):
        """Today total power usage in mW."""
        if self.insight_params:
            return self.insight_params['todaymw']

    @property
    def detail_state(self):
        """Return the state of the device."""
        if self.insight_params:
            standby_state = int(self.insight_params['state'])
            if standby_state == WEMO_ON:
                return STATE_ON
            elif standby_state == WEMO_OFF:
                return STATE_OFF
            elif standby_state == WEMO_STANDBY:
                return STATE_STANDBY
            else:
                return STATE_UNKNOWN

    @property
    def is_on(self):
        """Return true if switch is on. Standby is on."""
        return self._state

    @property
    def available(self):
        """True if switch is available."""
        if self.wemo.model_name == 'Insight' and self.insight_params is None:
            return False
        if self.wemo.model_name == 'Maker' and self.maker_params is None:
            return False
        return True

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._state = WEMO_ON
        self.update_ha_state()
        self.wemo.on()

    def turn_off(self):
        """Turn the switch off."""
        self._state = WEMO_OFF
        self.update_ha_state()
        self.wemo.off()

    def update(self):
        """Update WeMo state."""
        try:
            self._state = self.wemo.get_state(True)
            if self.wemo.model_name == 'Insight':
                self.insight_params = self.wemo.insight_params
                self.insight_params['standby_state'] = (
                    self.wemo.get_standby_state)
            elif self.wemo.model_name == 'Maker':
                self.maker_params = self.wemo.maker_params
        except AttributeError:
            _LOGGER.warning('Could not update status for %s', self.name)
