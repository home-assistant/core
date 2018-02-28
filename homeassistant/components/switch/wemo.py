"""
Support for WeMo switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.wemo/
"""
import logging
from datetime import datetime, timedelta

from homeassistant.components.switch import SwitchDevice
from homeassistant.util import convert
from homeassistant.const import (
    STATE_OFF, STATE_ON, STATE_STANDBY, STATE_UNKNOWN)
from homeassistant.loader import get_component

DEPENDENCIES = ['wemo']

_LOGGER = logging.getLogger(__name__)

ATTR_SENSOR_STATE = 'sensor_state'
ATTR_SWITCH_MODE = 'switch_mode'
ATTR_CURRENT_STATE_DETAIL = 'state_detail'
ATTR_COFFEMAKER_MODE = 'coffeemaker_mode'

MAKER_SWITCH_MOMENTARY = 'momentary'
MAKER_SWITCH_TOGGLE = 'toggle'

WEMO_ON = 1
WEMO_OFF = 0
WEMO_STANDBY = 8


# pylint: disable=unused-argument, too-many-function-args
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up discovered WeMo switches."""
    import pywemo.discovery as discovery

    if discovery_info is not None:
        location = discovery_info['ssdp_description']
        mac = discovery_info['mac_address']
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
        self.coffeemaker_mode = None
        self._state = None
        # look up model name once as it incurs network traffic
        self._model_name = self.wemo.model_name

        wemo = get_component('wemo')
        wemo.SUBSCRIPTION_REGISTRY.register(self.wemo)
        wemo.SUBSCRIPTION_REGISTRY.on(self.wemo, None, self._update_callback)

    def _update_callback(self, _device, _type, _params):
        """Update the state by the Wemo device."""
        _LOGGER.info("Subscription update for  %s", _device)
        updated = self.wemo.subscription_update(_type, _params)
        self._update(force_update=(not updated))

        if not hasattr(self, 'hass'):
            return
        self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed with subscriptions."""
        if self._model_name == 'Insight':
            return True
        return False

    @property
    def unique_id(self):
        """Return the ID of this WeMo switch."""
        return self.wemo.serialnumber

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

        if self.insight_params or (self.coffeemaker_mode is not None):
            attr[ATTR_CURRENT_STATE_DETAIL] = self.detail_state

        if self.insight_params:
            attr['on_latest_time'] = \
                WemoSwitch.as_uptime(self.insight_params['onfor'])
            attr['on_today_time'] = \
                WemoSwitch.as_uptime(self.insight_params['ontoday'])
            attr['on_total_time'] = \
                WemoSwitch.as_uptime(self.insight_params['ontotal'])
            attr['power_threshold_w'] = \
                convert(
                    self.insight_params['powerthreshold'], float, 0.0
                ) / 1000.0

        if self.coffeemaker_mode is not None:
            attr[ATTR_COFFEMAKER_MODE] = self.coffeemaker_mode

        return attr

    @staticmethod
    def as_uptime(_seconds):
        """Format seconds into uptime string in the format: 00d 00h 00m 00s."""
        uptime = datetime(1, 1, 1) + timedelta(seconds=_seconds)
        return "{:0>2d}d {:0>2d}h {:0>2d}m {:0>2d}s".format(
            uptime.day-1, uptime.hour, uptime.minute, uptime.second)

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        if self.insight_params:
            return convert(
                self.insight_params['currentpower'], float, 0.0
                ) / 1000.0

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        if self.insight_params:
            miliwatts = convert(self.insight_params['todaymw'], float, 0.0)
            return round(miliwatts / (1000.0 * 1000.0 * 60), 2)

    @property
    def detail_state(self):
        """Return the state of the device."""
        if self.coffeemaker_mode is not None:
            return self.wemo.mode_string
        if self.insight_params:
            standby_state = int(self.insight_params['state'])
            if standby_state == WEMO_ON:
                return STATE_ON
            elif standby_state == WEMO_OFF:
                return STATE_OFF
            elif standby_state == WEMO_STANDBY:
                return STATE_STANDBY
            return STATE_UNKNOWN

    @property
    def is_on(self):
        """Return true if switch is on. Standby is on."""
        return self._state

    @property
    def available(self):
        """Return true if switch is available."""
        if self._model_name == 'Insight' and self.insight_params is None:
            return False
        if self._model_name == 'Maker' and self.maker_params is None:
            return False
        if self._model_name == 'CoffeeMaker' and self.coffeemaker_mode is None:
            return False
        return True

    @property
    def icon(self):
        """Return the icon of device based on its type."""
        if self._model_name == 'CoffeeMaker':
            return 'mdi:coffee'
        return None

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._state = WEMO_ON
        self.wemo.on()
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._state = WEMO_OFF
        self.wemo.off()
        self.schedule_update_ha_state()

    def update(self):
        """Update WeMo state."""
        self._update(force_update=True)

    def _update(self, force_update=True):
        """Update the device state."""
        try:
            self._state = self.wemo.get_state(force_update)
            if self._model_name == 'Insight':
                self.insight_params = self.wemo.insight_params
                self.insight_params['standby_state'] = (
                    self.wemo.get_standby_state)
            elif self._model_name == 'Maker':
                self.maker_params = self.wemo.maker_params
            elif self._model_name == 'CoffeeMaker':
                self.coffeemaker_mode = self.wemo.mode
        except AttributeError as err:
            _LOGGER.warning("Could not update status for %s (%s)",
                            self.name, err)
