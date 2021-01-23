"""Support for WeMo switches."""
import asyncio
from datetime import datetime, timedelta
import logging

from pywemo.ouimeaux_device.api.service import ActionException

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON, STATE_STANDBY, STATE_UNKNOWN
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import convert

from .const import DOMAIN as WEMO_DOMAIN
from .entity import WemoSubscriptionEntity

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

# The WEMO_ constants below come from pywemo itself
ATTR_SENSOR_STATE = "sensor_state"
ATTR_SWITCH_MODE = "switch_mode"
ATTR_CURRENT_STATE_DETAIL = "state_detail"
ATTR_COFFEMAKER_MODE = "coffeemaker_mode"

MAKER_SWITCH_MOMENTARY = "momentary"
MAKER_SWITCH_TOGGLE = "toggle"

WEMO_ON = 1
WEMO_OFF = 0
WEMO_STANDBY = 8


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up WeMo switches."""

    async def _discovered_wemo(device):
        """Handle a discovered Wemo device."""
        async_add_entities([WemoSwitch(device)])

    async_dispatcher_connect(hass, f"{WEMO_DOMAIN}.switch", _discovered_wemo)

    await asyncio.gather(
        *[
            _discovered_wemo(device)
            for device in hass.data[WEMO_DOMAIN]["pending"].pop("switch")
        ]
    )


class WemoSwitch(WemoSubscriptionEntity, SwitchEntity):
    """Representation of a WeMo switch."""

    def __init__(self, device):
        """Initialize the WeMo switch."""
        super().__init__(device)
        self.insight_params = None
        self.maker_params = None
        self.coffeemaker_mode = None
        self._mode_string = None

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        if self.maker_params:
            # Is the maker sensor on or off.
            if self.maker_params["hassensor"]:
                # Note a state of 1 matches the WeMo app 'not triggered'!
                if self.maker_params["sensorstate"]:
                    attr[ATTR_SENSOR_STATE] = STATE_OFF
                else:
                    attr[ATTR_SENSOR_STATE] = STATE_ON

            # Is the maker switch configured as toggle(0) or momentary (1).
            if self.maker_params["switchmode"]:
                attr[ATTR_SWITCH_MODE] = MAKER_SWITCH_MOMENTARY
            else:
                attr[ATTR_SWITCH_MODE] = MAKER_SWITCH_TOGGLE

        if self.insight_params or (self.coffeemaker_mode is not None):
            attr[ATTR_CURRENT_STATE_DETAIL] = self.detail_state

        if self.insight_params:
            attr["on_latest_time"] = WemoSwitch.as_uptime(self.insight_params["onfor"])
            attr["on_today_time"] = WemoSwitch.as_uptime(self.insight_params["ontoday"])
            attr["on_total_time"] = WemoSwitch.as_uptime(self.insight_params["ontotal"])
            attr["power_threshold_w"] = (
                convert(self.insight_params["powerthreshold"], float, 0.0) / 1000.0
            )

        if self.coffeemaker_mode is not None:
            attr[ATTR_COFFEMAKER_MODE] = self.coffeemaker_mode

        return attr

    @staticmethod
    def as_uptime(_seconds):
        """Format seconds into uptime string in the format: 00d 00h 00m 00s."""
        uptime = datetime(1, 1, 1) + timedelta(seconds=_seconds)
        return "{:0>2d}d {:0>2d}h {:0>2d}m {:0>2d}s".format(
            uptime.day - 1, uptime.hour, uptime.minute, uptime.second
        )

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        if self.insight_params:
            return convert(self.insight_params["currentpower"], float, 0.0) / 1000.0

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        if self.insight_params:
            miliwatts = convert(self.insight_params["todaymw"], float, 0.0)
            return round(miliwatts / (1000.0 * 1000.0 * 60), 2)

    @property
    def detail_state(self):
        """Return the state of the device."""
        if self.coffeemaker_mode is not None:
            return self._mode_string
        if self.insight_params:
            standby_state = int(self.insight_params["state"])
            if standby_state == WEMO_ON:
                return STATE_ON
            if standby_state == WEMO_OFF:
                return STATE_OFF
            if standby_state == WEMO_STANDBY:
                return STATE_STANDBY
            return STATE_UNKNOWN

    @property
    def icon(self):
        """Return the icon of device based on its type."""
        if self.wemo.model_name == "CoffeeMaker":
            return "mdi:coffee"
        return None

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        try:
            if self.wemo.on():
                self._state = WEMO_ON
        except ActionException as err:
            _LOGGER.warning("Error while turning on device %s (%s)", self.name, err)
            self._available = False

        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        try:
            if self.wemo.off():
                self._state = WEMO_OFF
        except ActionException as err:
            _LOGGER.warning("Error while turning off device %s (%s)", self.name, err)
            self._available = False

        self.schedule_update_ha_state()

    def _update(self, force_update=True):
        """Update the device state."""
        try:
            self._state = self.wemo.get_state(force_update)

            if self.wemo.model_name == "Insight":
                self.insight_params = self.wemo.insight_params
                self.insight_params["standby_state"] = self.wemo.get_standby_state
            elif self.wemo.model_name == "Maker":
                self.maker_params = self.wemo.maker_params
            elif self.wemo.model_name == "CoffeeMaker":
                self.coffeemaker_mode = self.wemo.mode
                self._mode_string = self.wemo.mode_string

            if not self._available:
                _LOGGER.info("Reconnected to %s", self.name)
                self._available = True
        except (AttributeError, ActionException) as err:
            _LOGGER.warning("Could not update status for %s (%s)", self.name, err)
            self._available = False
            self.wemo.reconnect_with_device()
