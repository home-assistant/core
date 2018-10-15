"""
Integration with the Rachio Iro sprinkler system controller.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.rachio/
"""
from abc import abstractmethod
from datetime import timedelta
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.components.rachio import (CONF_MANUAL_RUN_MINS,
                                             DOMAIN as DOMAIN_RACHIO,
                                             KEY_DEVICE_ID,
                                             KEY_ENABLED,
                                             KEY_ID,
                                             KEY_NAME,
                                             KEY_ON,
                                             KEY_SUBTYPE,
                                             KEY_SUMMARY,
                                             KEY_ZONE_ID,
                                             KEY_ZONE_NUMBER,
                                             SIGNAL_RACHIO_CONTROLLER_UPDATE,
                                             SIGNAL_RACHIO_ZONE_UPDATE,
                                             SUBTYPE_ZONE_STARTED,
                                             SUBTYPE_ZONE_STOPPED,
                                             SUBTYPE_ZONE_COMPLETED,
                                             SUBTYPE_SLEEP_MODE_ON,
                                             SUBTYPE_SLEEP_MODE_OFF)
from homeassistant.helpers.dispatcher import dispatcher_connect

DEPENDENCIES = ['rachio']

_LOGGER = logging.getLogger(__name__)

ATTR_ZONE_SUMMARY = 'Summary'
ATTR_ZONE_NUMBER = 'Zone number'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Rachio switches."""
    manual_run_time = timedelta(minutes=hass.data[DOMAIN_RACHIO].config.get(
        CONF_MANUAL_RUN_MINS))
    _LOGGER.info("Rachio run time is %s", str(manual_run_time))

    # Add all zones from all controllers as switches
    devices = []
    for controller in hass.data[DOMAIN_RACHIO].controllers:
        devices.append(RachioStandbySwitch(hass, controller))

        for zone in controller.list_zones():
            devices.append(RachioZone(hass, controller, zone, manual_run_time))

    add_entities(devices)
    _LOGGER.info("%d Rachio switch(es) added", len(devices))


class RachioSwitch(SwitchDevice):
    """Represent a Rachio state that can be toggled."""

    def __init__(self, controller, poll=True):
        """Initialize a new Rachio switch."""
        self._controller = controller

        if poll:
            self._state = self._poll_update()
        else:
            self._state = None

    @property
    def should_poll(self) -> bool:
        """Declare that this entity pushes its state to HA."""
        return False

    @property
    def name(self) -> str:
        """Get a name for this switch."""
        return "Switch on {}".format(self._controller.name)

    @property
    def is_on(self) -> bool:
        """Return whether the switch is currently on."""
        return self._state

    @abstractmethod
    def _poll_update(self, data=None) -> bool:
        """Poll the API."""
        pass

    def _handle_any_update(self, *args, **kwargs) -> None:
        """Determine whether an update event applies to this device."""
        if args[0][KEY_DEVICE_ID] != self._controller.controller_id:
            # For another device
            return

        # For this device
        self._handle_update(args, kwargs)

    @abstractmethod
    def _handle_update(self, *args, **kwargs) -> None:
        """Handle incoming webhook data."""
        pass


class RachioStandbySwitch(RachioSwitch):
    """Representation of a standby status/button."""

    def __init__(self, hass, controller):
        """Instantiate a new Rachio standby mode switch."""
        dispatcher_connect(hass, SIGNAL_RACHIO_CONTROLLER_UPDATE,
                           self._handle_any_update)
        super().__init__(controller, poll=False)
        self._poll_update(controller.init_data)

    @property
    def name(self) -> str:
        """Return the name of the standby switch."""
        return "{} in standby mode".format(self._controller.name)

    @property
    def unique_id(self) -> str:
        """Return a unique id by combinining controller id and purpose."""
        return "{}-standby".format(self._controller.controller_id)

    @property
    def icon(self) -> str:
        """Return an icon for the standby switch."""
        return "mdi:power"

    def _poll_update(self, data=None) -> bool:
        """Request the state from the API."""
        if data is None:
            data = self._controller.rachio.device.get(
                self._controller.controller_id)[1]

        return not data[KEY_ON]

    def _handle_update(self, *args, **kwargs) -> None:
        """Update the state using webhook data."""
        if args[0][KEY_SUBTYPE] == SUBTYPE_SLEEP_MODE_ON:
            self._state = True
        elif args[0][KEY_SUBTYPE] == SUBTYPE_SLEEP_MODE_OFF:
            self._state = False

        self.schedule_update_ha_state()

    def turn_on(self, **kwargs) -> None:
        """Put the controller in standby mode."""
        self._controller.rachio.device.off(self._controller.controller_id)

    def turn_off(self, **kwargs) -> None:
        """Resume controller functionality."""
        self._controller.rachio.device.on(self._controller.controller_id)


class RachioZone(RachioSwitch):
    """Representation of one zone of sprinklers connected to the Rachio Iro."""

    def __init__(self, hass, controller, data, manual_run_time):
        """Initialize a new Rachio Zone."""
        self._id = data[KEY_ID]
        self._zone_name = data[KEY_NAME]
        self._zone_number = data[KEY_ZONE_NUMBER]
        self._zone_enabled = data[KEY_ENABLED]
        self._manual_run_time = manual_run_time
        self._summary = str()
        super().__init__(controller)

        # Listen for all zone updates
        dispatcher_connect(hass, SIGNAL_RACHIO_ZONE_UPDATE,
                           self._handle_update)

    def __str__(self):
        """Display the zone as a string."""
        return 'Rachio Zone "{}" on {}'.format(self.name,
                                               str(self._controller))

    @property
    def zone_id(self) -> str:
        """How the Rachio API refers to the zone."""
        return self._id

    @property
    def name(self) -> str:
        """Return the friendly name of the zone."""
        return self._zone_name

    @property
    def unique_id(self) -> str:
        """Return a unique id by combinining controller id and zone number."""
        return "{}-zone-{}".format(self._controller.controller_id,
                                   self.zone_id)

    @property
    def icon(self) -> str:
        """Return the icon to display."""
        return "mdi:water"

    @property
    def zone_is_enabled(self) -> bool:
        """Return whether the zone is allowed to run."""
        return self._zone_enabled

    @property
    def state_attributes(self) -> dict:
        """Return the optional state attributes."""
        return {
            ATTR_ZONE_NUMBER: self._zone_number,
            ATTR_ZONE_SUMMARY: self._summary,
        }

    def turn_on(self, **kwargs) -> None:
        """Start watering this zone."""
        # Stop other zones first
        self.turn_off()

        # Start this zone
        self._controller.rachio.zone.start(self.zone_id,
                                           self._manual_run_time.seconds)
        _LOGGER.debug("Watering %s on %s", self.name, self._controller.name)

    def turn_off(self, **kwargs) -> None:
        """Stop watering all zones."""
        self._controller.stop_watering()

    def _poll_update(self, data=None) -> bool:
        """Poll the API to check whether the zone is running."""
        schedule = self._controller.current_schedule
        return self.zone_id == schedule.get(KEY_ZONE_ID)

    def _handle_update(self, *args, **kwargs) -> None:
        """Handle incoming webhook zone data."""
        if args[0][KEY_ZONE_ID] != self.zone_id:
            return

        self._summary = kwargs.get(KEY_SUMMARY, str())

        if args[0][KEY_SUBTYPE] == SUBTYPE_ZONE_STARTED:
            self._state = True
        elif args[0][KEY_SUBTYPE] in [SUBTYPE_ZONE_STOPPED,
                                      SUBTYPE_ZONE_COMPLETED]:
            self._state = False

        self.schedule_update_ha_state()
