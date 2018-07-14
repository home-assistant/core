"""
Support for Ecovacs Ecovacs Vaccums.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/vacuum.neato/
"""
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

SUPPORT_ECOVACS = (
    SUPPORT_BATTERY | SUPPORT_RETURN_HOME | SUPPORT_CLEAN_SPOT |
    SUPPORT_STOP | SUPPORT_TURN_OFF | SUPPORT_TURN_ON | SUPPORT_LOCATE |
    SUPPORT_STATUS | SUPPORT_SEND_COMMAND | SUPPORT_FAN_SPEED)

ECOVACS_FAN_SPEED_LIST = ['normal', 'high']

# These consts represent bot statuses that can come from the `sucks` library
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

ATTR_ERROR = 'error'
ATTR_COMPONENT_PREFIX = 'component_'


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

        self._fan_speed = None
        self._error = None
        _LOGGER.debug("Vacuum initialized: %s", self.name)

    async def async_added_to_hass(self) -> None:
        """d."""
        # Fire off some queries to get initial state
        self.device.statusEvents.subscribe(self.on_status)
        self.device.batteryEvents.subscribe(self.on_battery)
        self.device.errorEvents.subscribe(self.on_error)
        self.device.lifespanEvents.subscribe(self.on_lifespan)

    def on_status(self, status):
        """Handle the status of the robot changing."""
        self.schedule_update_ha_state()

    def on_battery(self, battery_level):
        """Handle the battery level changing on the robot."""
        self.schedule_update_ha_state()

    def on_lifespan(self, lifespan):
        """Handle component lifespan reports from the robot."""
        self.schedule_update_ha_state()

    def on_error(self, error):
        """Handle an error event from the robot.

        This will not change the entity's state. If the error caused the state
        to change, that will come through as a separate on_status event
        """
        if error == 'no_error':
            self._error = None
        else:
            self._error = error

        self.hass.bus.fire('ecovacs_error', {
            'entity_id': self.entity_id,
            'error': error
        })
        self.schedule_update_ha_state()

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return False

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        if hasattr(self.device.vacuum, 'did'):
            # `did` is the Ecovacs-reported Device ID
            return self.device.vacuum['did']
        return None

    @property
    def is_on(self):
        """Return true if vacuum is currently cleaning."""
        return self.device.vacuum_status in STATUSES_CLEANING

    @property
    def is_charging(self):
        """Return true if vacuum is currently charging."""
        return self.device.vacuum_status in STATUSES_CHARGING

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_ECOVACS

    @property
    def status(self):
        """Return the status of the vacuum cleaner."""
        return self.device.vacuum_status

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
        if self.device.battery_status is not None:
            return self.device.battery_status * 100

        return super().battery_level

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        return self.device.fan_speed

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
        from sucks import PlaySound
        self.device.run(PlaySound())

    def set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if self.is_on:
            from sucks import Clean
            self.device.run(Clean(
                mode=self.device.clean_status, speed=fan_speed))

    def send_command(self, command, params=None, **kwargs):
        """Send a command to a vacuum cleaner."""
        from sucks import VacBotCommand
        self.device.run(VacBotCommand(command, params))

    @property
    def state_attributes(self):
        """Return the state attributes of the vacuum cleaner."""
        data = super().state_attributes

        data[ATTR_ERROR] = self._error

        for key, val in self.device.components.items():
            attr_name = ATTR_COMPONENT_PREFIX + key
            data[attr_name] = int(val * 100)

        return data
