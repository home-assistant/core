"""Support for Ecovacs Ecovacs Vaccums."""
import logging

import sucks

from homeassistant.components.vacuum import (
    SUPPORT_BATTERY,
    SUPPORT_CLEAN_SPOT,
    SUPPORT_FAN_SPEED,
    SUPPORT_LOCATE,
    SUPPORT_RETURN_HOME,
    SUPPORT_SEND_COMMAND,
    SUPPORT_STATUS,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    VacuumEntity,
)
from homeassistant.helpers.icon import icon_for_battery_level

from . import ECOVACS_DEVICES

_LOGGER = logging.getLogger(__name__)

SUPPORT_ECOVACS = (
    SUPPORT_BATTERY
    | SUPPORT_RETURN_HOME
    | SUPPORT_CLEAN_SPOT
    | SUPPORT_STOP
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
    | SUPPORT_LOCATE
    | SUPPORT_STATUS
    | SUPPORT_SEND_COMMAND
    | SUPPORT_FAN_SPEED
)

ATTR_ERROR = "error"
ATTR_COMPONENT_PREFIX = "component_"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ecovacs vacuums."""
    vacuums = []
    for device in hass.data[ECOVACS_DEVICES]:
        vacuums.append(EcovacsVacuum(device))
    _LOGGER.debug("Adding Ecovacs Vacuums to Home Assistant: %s", vacuums)
    add_entities(vacuums, True)


class EcovacsVacuum(VacuumEntity):
    """Ecovacs Vacuums such as Deebot."""

    def __init__(self, device):
        """Initialize the Ecovacs Vacuum."""
        self.device = device
        self.device.connect_and_wait_until_ready()
        if self.device.vacuum.get("nick") is not None:
            self._name = str(self.device.vacuum["nick"])
        else:
            # In case there is no nickname defined, use the device id
            self._name = str(format(self.device.vacuum["did"]))

        self._fan_speed = None
        self._error = None
        _LOGGER.debug("Vacuum initialized: %s", self.name)

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        self.device.statusEvents.subscribe(lambda _: self.schedule_update_ha_state())
        self.device.batteryEvents.subscribe(lambda _: self.schedule_update_ha_state())
        self.device.lifespanEvents.subscribe(lambda _: self.schedule_update_ha_state())
        self.device.errorEvents.subscribe(self.on_error)

    def on_error(self, error):
        """Handle an error event from the robot.

        This will not change the entity's state. If the error caused the state
        to change, that will come through as a separate on_status event
        """
        if error == "no_error":
            self._error = None
        else:
            self._error = error

        self.hass.bus.fire(
            "ecovacs_error", {"entity_id": self.entity_id, "error": error}
        )
        self.schedule_update_ha_state()

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return False

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return self.device.vacuum.get("did")

    @property
    def is_on(self):
        """Return true if vacuum is currently cleaning."""
        return self.device.is_cleaning

    @property
    def is_charging(self):
        """Return true if vacuum is currently charging."""
        return self.device.is_charging

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

        self.device.run(sucks.Charge())

    @property
    def battery_icon(self):
        """Return the battery icon for the vacuum cleaner."""
        return icon_for_battery_level(
            battery_level=self.battery_level, charging=self.is_charging
        )

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

        return [sucks.FAN_SPEED_NORMAL, sucks.FAN_SPEED_HIGH]

    def turn_on(self, **kwargs):
        """Turn the vacuum on and start cleaning."""

        self.device.run(sucks.Clean())

    def turn_off(self, **kwargs):
        """Turn the vacuum off stopping the cleaning and returning home."""
        self.return_to_base()

    def stop(self, **kwargs):
        """Stop the vacuum cleaner."""

        self.device.run(sucks.Stop())

    def clean_spot(self, **kwargs):
        """Perform a spot clean-up."""

        self.device.run(sucks.Spot())

    def locate(self, **kwargs):
        """Locate the vacuum cleaner."""

        self.device.run(sucks.PlaySound())

    def set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if self.is_on:

            self.device.run(sucks.Clean(mode=self.device.clean_status, speed=fan_speed))

    def send_command(self, command, params=None, **kwargs):
        """Send a command to a vacuum cleaner."""
        self.device.run(sucks.VacBotCommand(command, params))

    @property
    def extra_state_attributes(self):
        """Return the device-specific state attributes of this vacuum."""
        data = {}
        data[ATTR_ERROR] = self._error

        for key, val in self.device.components.items():
            attr_name = ATTR_COMPONENT_PREFIX + key
            data[attr_name] = int(val * 100)

        return data
