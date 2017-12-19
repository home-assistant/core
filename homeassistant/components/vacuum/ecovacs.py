"""
Support for Ecovacs Ecovacs Vaccums.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/vacuum.neato/
"""
import logging

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.components.vacuum import (
    VacuumDevice, SUPPORT_BATTERY, SUPPORT_PAUSE, SUPPORT_RETURN_HOME,
    SUPPORT_STATUS, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON)
from homeassistant.components.ecovacs import (
    ECOVACS_DEVICES)
from homeassistant.helpers.icon import icon_for_battery_level

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['ecovacs']

SUPPORT_ECOVACS = SUPPORT_BATTERY | SUPPORT_PAUSE | SUPPORT_RETURN_HOME | \
                 SUPPORT_STOP | SUPPORT_TURN_OFF | SUPPORT_TURN_ON | \
                 SUPPORT_STATUS

ECOVACS_FAN_SPEED_LIST = ['standard', 'strong']

ICON = "mdi:roomba"

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Ecovacs vacuums."""
    vacuums = []
    for device in hass.data[ECOVACS_DEVICES]:
        vacuums.append(EcovacsVacuum(device))
    _LOGGER.debug("Adding Ecovacs Vacuums to Hass: %s", vacuums)
    add_devices(vacuums, True)


class EcovacsVacuum(VacuumDevice):
    """Ecovacs Vacuums such as Deebot."""

    def __init__(self, device):
        """Initialize the Ecovacs Vacuum."""
        self.device = device
        self.device.connect_and_wait_until_ready()
        try:
            self._name = '{}'.format(self.device.vacuum['nick'])
        except KeyError:
            # In case there is no nickname defined, use the device id
            self._name = '{}'.format(self.device.vacuum['did'])

        self._clean_status = None
        self._charge_status = None
        self._battery_level = None
        self._state = None
        self._first_update_done = False
        _LOGGER.debug("Vacuum initialized: %s", self.name)

    def update(self):
        if not self._first_update_done:
            from sucks import VacBotCommand
            # Fire off some queries to get initial state
            self.device.run(VacBotCommand('GetCleanState', {}))
            self.device.run(VacBotCommand('GetChargeState', {}))
            self.device.run(VacBotCommand('GetBatteryInfo', {}))
            self._first_update_done = True

        self._clean_status = self.device.clean_status
        self._charge_status = self.device.charge_status

        try:
            if self.device.battery_status is not None:
                self._battery_level = self.device.battery_status * 100
        except AttributeError:
            # No battery_status property
            pass

    @property
    def is_on(self):
        """Return true if vacuum is currently cleaning."""
        if self._clean_status is None:
            return False
        else:
            return self._clean_status != 'stop'

    @property
    def is_charging(self):
        """Return true if vacuum is currently charging."""
        if self._charge_status is None:
            return False
        else:
            return self._charge_status == 'charging'

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device."""
        return ICON

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_ECOVACS

    def return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        from sucks import Charge
        self.device.run(Charge())

    @property
    def battery_icon(self):
        """Return the battery icon for the vacuum cleaner."""
        return icon_for_battery_level(
            battery_level=self.battery_level, charging=self.is_charging)

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self._battery_level

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        # TODO: Implement
        return None

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return ECOVACS_FAN_SPEED_LIST

    def turn_on(self, **kwargs):
        """Turn the vacuum on and start cleaning."""
        from sucks import Clean
        self.device.run(Clean(False))

    def turn_off(self, **kwargs):
        """Turn the vacuum off stopping the cleaning and returning home."""
        self.return_to_base()

    def stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        from sucks import VacBotCommand
        self.device.run(VacBotCommand('Move', {'action': 'stop'}))

    def clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        # TODO: Implement
        raise NotImplementedError()

    def locate(self, **kwargs):
        """Locate the vacuum cleaner."""
        # TODO: Implement
        raise NotImplementedError()

    def set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        # TODO: Implement
        raise NotImplementedError()

    def start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task."""
        # TODO: Implement
        raise NotImplementedError()

    def send_command(self, command, params=None, **kwargs):
        """Send a command to a vacuum cleaner."""
        # TODO: Implement
        raise NotImplementedError()

    @property
    def state_attributes(self):
        """Return the state attributes of the vacuum cleaner."""
        # TODO: Implement
        data = super().state_attributes

        # TODO: attribute names should be consts
        data['clean_status'] = self._clean_status
        data['charge_status'] = self._charge_status

        return data
