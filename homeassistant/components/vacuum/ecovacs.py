"""
Support for Ecovacs Ecovacs Vaccums.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/vacuum.neato/
"""
import asyncio
import logging

from homeassistant.components.vacuum import (
    VacuumDevice, SUPPORT_BATTERY, SUPPORT_RETURN_HOME, SUPPORT_CLEAN_SPOT,
    SUPPORT_STATUS, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_LOCATE, SUPPORT_FAN_SPEED, SUPPORT_SEND_COMMAND, )
from homeassistant.components.ecovacs import (
    ECOVACS_DEVICES)
from homeassistant.helpers.icon import icon_for_battery_level

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['ecovacs']

# Note: SUPPORT_FAN_SPEED gets dynamically added to this list based on vacuum
# state in the supported_features Property getter
SUPPORT_ECOVACS = (
    SUPPORT_BATTERY | SUPPORT_RETURN_HOME | SUPPORT_CLEAN_SPOT |
    SUPPORT_STOP | SUPPORT_TURN_OFF | SUPPORT_TURN_ON |
    SUPPORT_STATUS | SUPPORT_LOCATE | SUPPORT_SEND_COMMAND)

ECOVACS_FAN_SPEED_LIST = ['normal', 'high']

# These consts represent bot statuses that can come from the `sucks` library
# TODO: These should probably be exposed in the sucks library and just imported
STATUS_AUTO = 'auto'
STATUS_EDGE = 'edge'
STATUS_SPOT = 'spot'
STATUS_SINGLE_ROOM = 'single_room'
STATUS_STOP = 'stop'
STATUS_RETURNING = 'returning'
STATUS_CHARGING = 'charging'
STATUS_IDLE = 'idle'
STATUS_ERROR = 'error'

# Any status that represents active cleaning
STATUSES_CLEANING = [STATUS_AUTO, STATUS_EDGE, STATUS_SPOT, STATUS_SINGLE_ROOM]
# Any status that represents sitting on the charger
STATUSES_CHARGING = [STATUS_CHARGING, STATUS_IDLE]

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

        self._status = None
        self._fan_speed = None
        self._battery_level = None
        _LOGGER.debug("Vacuum initialized: %s", self.name)

    @asyncio.coroutine
    def async_added_to_hass(self) -> None:
        # Fire off some queries to get initial state
        from sucks import VacBotCommand
        self.device.statusEvents.subscribe(self.on_status)
        self.device.batteryEvents.subscribe(self.on_battery)
        self.device.errorEvents.subscribe(self.on_error)

        # TODO: Once sucks does internal state handling, these shouldn't be
        # TODO: necessary. Perhaps this will be replaced by a single call to
        # TODO: turn on state handling, or turn on each feature to track?
        self.device.run(VacBotCommand('GetCleanState', {}))
        self.device.run(VacBotCommand('GetChargeState', {}))
        self.device.run(VacBotCommand('GetBatteryInfo', {}))

    def on_status(self, status):
        """Handle the status of the robot changing."""
        self._status = status
        self.schedule_update_ha_state()

    def on_battery(self, battery_level):
        """Handle the battery level changing on the robot."""
        self._battery_level = battery_level * 100
        self.schedule_update_ha_state()

    def on_error(self, error):
        """Handle an error event from the robot.

        This will not change the entity's state. If the error caused the state
        to change, that will come through as a separate on_status event
        """
        self.hass.bus.fire('ecovacs_error', {
            'entity_id': self.entity_id,
            'error': error
        })

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.
        """
        return False

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        if hasattr(self.device.vacuum, 'did'):
            return self.device.vacuum['did']
        return None

    @property
    def is_on(self):
        """Return true if vacuum is currently cleaning."""
        return self._status in STATUSES_CLEANING

    @property
    def is_charging(self):
        """Return true if vacuum is currently charging."""
        return self._status in STATUSES_CHARGING

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
        support = SUPPORT_ECOVACS
        if self.is_on:
            # Fan speed can only be adjusted while cleaning
            support = support | SUPPORT_FAN_SPEED

        return support

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
        return self._fan_speed

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return ECOVACS_FAN_SPEED_LIST

    def turn_on(self, **kwargs):
        """Turn the vacuum on and start cleaning."""
        from sucks import Clean
        self.device.run(Clean())

    def turn_off(self, **kwargs):
        """Turn the vacuum off stopping the cleaning and returning home."""
        self.return_to_base()

    def stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        from sucks import Stop
        self.device.run(Stop())

    def clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        from sucks import Spot
        self.device.run(Spot())

    def locate(self, **kwargs):
        """Locate the vacuum cleaner."""
        raise NotImplementedError()

        # TODO: Needs support in sucks library
        from sucks import Locate
        self.device.run(Locate())

    def set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if self.is_on:
            from sucks import Clean
            self.device.run(Clean(
                mode=self._status, speed=fan_speed))

    def send_command(self, command, params=None, **kwargs):
        """Send a command to a vacuum cleaner."""
        from sucks import VacBotCommand
        self.device.run(VacBotCommand(command, params))

    @property
    def state_attributes(self):
        """Return the state attributes of the vacuum cleaner."""
        data = super().state_attributes

        # TODO: attribute names should be consts
        data['status'] = self._status

        return data
