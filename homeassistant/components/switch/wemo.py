"""
Support for WeMo switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.wemo/
"""
import logging
from datetime import datetime, timedelta

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    STATE_OFF, STATE_ON, STATE_STANDBY, STATE_UNKNOWN)
from homeassistant.loader import get_component

DEPENDENCIES = ['wemo']

_LOGGER = logging.getLogger(__name__)

ATTR_SENSOR_STATE = "sensor_state"
ATTR_SWITCH_MODE = "switch_mode"
ATTR_CURRENT_STATE_DETAIL = 'state_detail'
ATTR_COFFEMAKER_MODE = "coffeemaker_mode"

# Wemo Insight
ATTR_POWER_CURRENT_W = 'power_current_w'
# ATTR_POWER_AVG_W = 'power_average_w'
ATTR_POWER_TODAY_MW_MIN = 'power_today_mW_min'
ATTR_POWER_TOTAL_MW_MIN = 'power_total_mW_min'
ATTR_ON_FOR_TIME = 'on_time_most_recent'
ATTR_ON_TODAY_TIME = 'on_time_today'
ATTR_ON_TOTAL_TIME = 'on_time_total'
ATTR_POWER_THRESHOLD = 'power_threshold_w'

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
        self.coffeemaker_mode = None
        self._state = None
        # look up model name once as it incurs network traffic
        self._model_name = self.wemo.model_name

        wemo = get_component('wemo')
        wemo.SUBSCRIPTION_REGISTRY.register(self.wemo)
        wemo.SUBSCRIPTION_REGISTRY.on(self.wemo, None, self._update_callback)

    def _update_callback(self, _device, _params):
        """Called by the Wemo device callback to update state."""
        _LOGGER.info(
            'Subscription update for  %s',
            _device)
        if self._model_name == 'CoffeeMaker':
            self.wemo.subscription_callback(_params)
            self._update(force_update=False)
        else:
            self.update()
        if not hasattr(self, 'hass'):
            return
        self.schedule_update_ha_state()

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

        if self.insight_params or (self.coffeemaker_mode is not None):
            attr[ATTR_CURRENT_STATE_DETAIL] = self.detail_state
            attr[ATTR_POWER_CURRENT_W] = self.power_current_watt
            # attr[ATTR_POWER_AVG_W] = self.power_average_watt
            attr[ATTR_POWER_TODAY_MW_MIN] = self.power_today_mw_min
            attr[ATTR_POWER_TOTAL_MW_MIN] = self.power_total_mw_min
            attr[ATTR_ON_FOR_TIME] = self.on_for
            attr[ATTR_ON_TODAY_TIME] = self.on_today
            attr[ATTR_ON_TOTAL_TIME] = self.on_total
            attr[ATTR_POWER_THRESHOLD] = self.power_threshold

        if self.coffeemaker_mode is not None:
            attr[ATTR_COFFEMAKER_MODE] = self.coffeemaker_mode

        return attr

#    @property
    def _current_power_mw(self):
        """Current power usage in mW."""
        if self.insight_params:
            return self.insight_params['currentpower']

    @property
    def power_current_watt(self):
        """Current power usage in W."""
        if self.insight_params:
            try:
                return self._current_power_mw() / 1000
            except Exception:
                return None

    @property
    def power_threshold(self):
        """Threshold of W at which Insight will indicate it's load is ON."""
        if self.insight_params:
            return self.insight_params['powerthreshold'] / 1000

    @staticmethod
    def as_uptime(_seconds):
        """Format seconds in to uptime string in the format: 00d 00h 00m 00s """
        uptime = datetime(1, 1, 1) + timedelta(seconds=_seconds)
        return "{:0>2d}d {:0>2d}h {:0>2d}m {:0>2d}s".format(uptime.day-1,
                                                            uptime.hour,
                                                            uptime.minute,
                                                            uptime.second)

    @property
    def on_for(self):
        """On time in seconds."""
        if self.insight_params:
            return WemoSwitch.as_uptime(self.insight_params['onfor'])

    @property
    def on_today(self):
        """On time in seconds."""
        if self.insight_params:
            return WemoSwitch.as_uptime(self.insight_params['ontoday'])

    @property
    def on_total(self):
        """On time in seconds."""
        if self.insight_params:
            return WemoSwitch.as_uptime(self.insight_params['ontotal'])

    @property
    def power_total_mw_min(self):
        """Total of average mW per minute."""
        if self.insight_params:
            try:
                return self.insight_params['totalmw']
            except Exception:
                return None

    @property
    def power_today_mw_min(self):
        """Total consumption today in mW per minute."""
        if self.insight_params:
            try:
                return self.insight_params['todaymw']
            except Exception:
                return None

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
            else:
                return STATE_UNKNOWN

    @property
    def is_on(self):
        """Return true if switch is on. Standby is on."""
        return self._state

    @property
    def available(self):
        """True if switch is available."""
        if self._model_name == 'Insight' and self.insight_params is None:
            return False
        if self._model_name == 'Maker' and self.maker_params is None:
            return False
        if self._model_name == 'CoffeeMaker' and self.coffeemaker_mode is None:
            return False
        return True

    @property
    def icon(self):
        """Icon of device based on its type."""
        if self._model_name == 'CoffeeMaker':
            return 'mdi:coffee'
        else:
            return super().icon

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._state = WEMO_ON
        self.wemo.on()
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn the switch off."""
        self._state = WEMO_OFF
        self.wemo.off()
        self.schedule_update_ha_state()

    def update(self):
        """Update WeMo state."""
        self._update(force_update=True)

    def _update(self, force_update=True):
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
        except AttributeError:
            _LOGGER.warning('Could not update status for %s', self.name)
