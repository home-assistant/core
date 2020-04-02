"""Integration with the Rachio Iro sprinkler system controller."""
from abc import abstractmethod
from datetime import timedelta
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    ATTR_ZONE_SHADE,
    ATTR_ZONE_TYPE,
    CONF_MANUAL_RUN_MINS,
    DEFAULT_MANUAL_RUN_MINS,
    DOMAIN as DOMAIN_RACHIO,
    KEY_CUSTOM_CROP,
    KEY_CUSTOM_SHADE,
    KEY_DEVICE_ID,
    KEY_DURATION,
    KEY_ENABLED,
    KEY_ID,
    KEY_IMAGE_URL,
    KEY_NAME,
    KEY_ON,
    KEY_SCHEDULE_ID,
    KEY_SUBTYPE,
    KEY_SUMMARY,
    KEY_ZONE_ID,
    KEY_ZONE_NUMBER,
    SIGNAL_RACHIO_CONTROLLER_UPDATE,
    SIGNAL_RACHIO_SCHEDULE_UPDATE,
    SIGNAL_RACHIO_ZONE_UPDATE,
)
from .entity import RachioDevice
from .webhooks import (
    SUBTYPE_SCHEDULE_COMPLETED,
    SUBTYPE_SCHEDULE_STARTED,
    SUBTYPE_SCHEDULE_STOPPED,
    SUBTYPE_SLEEP_MODE_OFF,
    SUBTYPE_SLEEP_MODE_ON,
    SUBTYPE_ZONE_COMPLETED,
    SUBTYPE_ZONE_STARTED,
    SUBTYPE_ZONE_STOPPED,
)

_LOGGER = logging.getLogger(__name__)

ATTR_ZONE_SUMMARY = "Summary"
ATTR_ZONE_NUMBER = "Zone number"
ATTR_SCHEDULE_SUMMARY = "Summary"
ATTR_SCHEDULE_ENABLED = "Enabled"
ATTR_SCHEDULE_DURATION = "Duration"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Rachio switches."""
    # Add all zones from all controllers as switches
    entities = await hass.async_add_executor_job(_create_entities, hass, config_entry)
    async_add_entities(entities)
    _LOGGER.info("%d Rachio switch(es) added", len(entities))


def _create_entities(hass, config_entry):
    entities = []
    person = hass.data[DOMAIN_RACHIO][config_entry.entry_id]
    # Fetch the schedule once at startup
    # in order to avoid every zone doing it
    for controller in person.controllers:
        entities.append(RachioStandbySwitch(controller))
        zones = controller.list_zones()
        schedules = controller.list_schedules()
        flex_schedules = controller.list_flex_schedules()
        current_schedule = controller.current_schedule
        for zone in zones:
            entities.append(RachioZone(person, controller, zone, current_schedule))
        for sched in schedules + flex_schedules:
            entities.append(RachioSchedule(person, controller, sched, current_schedule))
    _LOGGER.debug("Added %s", entities)
    return entities


class RachioSwitch(RachioDevice, SwitchDevice):
    """Represent a Rachio state that can be toggled."""

    def __init__(self, controller, poll=True):
        """Initialize a new Rachio switch."""
        super().__init__(controller)

        if poll:
            self._state = self._poll_update()
        else:
            self._state = None

    @property
    def name(self) -> str:
        """Get a name for this switch."""
        return f"Switch on {self._controller.name}"

    @property
    def is_on(self) -> bool:
        """Return whether the switch is currently on."""
        return self._state

    @abstractmethod
    def _poll_update(self, data=None) -> bool:
        """Poll the API."""

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


class RachioStandbySwitch(RachioSwitch):
    """Representation of a standby status/button."""

    def __init__(self, controller):
        """Instantiate a new Rachio standby mode switch."""
        super().__init__(controller, poll=True)
        self._poll_update(controller.init_data)

    @property
    def name(self) -> str:
        """Return the name of the standby switch."""
        return f"{self._controller.name} in standby mode"

    @property
    def unique_id(self) -> str:
        """Return a unique id by combining controller id and purpose."""
        return f"{self._controller.controller_id}-standby"

    @property
    def icon(self) -> str:
        """Return an icon for the standby switch."""
        return "mdi:power"

    def _poll_update(self, data=None) -> bool:
        """Request the state from the API."""
        if data is None:
            data = self._controller.rachio.device.get(self._controller.controller_id)[1]

        return not data[KEY_ON]

    def _handle_update(self, *args, **kwargs) -> None:
        """Update the state using webhook data."""
        if args[0][0][KEY_SUBTYPE] == SUBTYPE_SLEEP_MODE_ON:
            self._state = True
        elif args[0][0][KEY_SUBTYPE] == SUBTYPE_SLEEP_MODE_OFF:
            self._state = False

        self.schedule_update_ha_state()

    def turn_on(self, **kwargs) -> None:
        """Put the controller in standby mode."""
        self._controller.rachio.device.off(self._controller.controller_id)

    def turn_off(self, **kwargs) -> None:
        """Resume controller functionality."""
        self._controller.rachio.device.on(self._controller.controller_id)

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_RACHIO_CONTROLLER_UPDATE, self._handle_any_update
            )
        )


class RachioZone(RachioSwitch):
    """Representation of one zone of sprinklers connected to the Rachio Iro."""

    def __init__(self, person, controller, data, current_schedule):
        """Initialize a new Rachio Zone."""
        self._id = data[KEY_ID]
        self._zone_name = data[KEY_NAME]
        self._zone_number = data[KEY_ZONE_NUMBER]
        self._zone_enabled = data[KEY_ENABLED]
        self._entity_picture = data.get(KEY_IMAGE_URL)
        self._person = person
        self._shade_type = data.get(KEY_CUSTOM_SHADE, {}).get(KEY_NAME)
        self._zone_type = data.get(KEY_CUSTOM_CROP, {}).get(KEY_NAME)
        self._summary = str()
        self._current_schedule = current_schedule
        super().__init__(controller, poll=False)
        self._state = self.zone_id == self._current_schedule.get(KEY_ZONE_ID)
        self._undo_dispatcher = None

    def __str__(self):
        """Display the zone as a string."""
        return 'Rachio Zone "{}" on {}'.format(self.name, str(self._controller))

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
        """Return a unique id by combining controller id and zone number."""
        return f"{self._controller.controller_id}-zone-{self.zone_id}"

    @property
    def icon(self) -> str:
        """Return the icon to display."""
        return "mdi:water"

    @property
    def zone_is_enabled(self) -> bool:
        """Return whether the zone is allowed to run."""
        return self._zone_enabled

    @property
    def entity_picture(self):
        """Return the entity picture to use in the frontend, if any."""
        return self._entity_picture

    @property
    def state_attributes(self) -> dict:
        """Return the optional state attributes."""
        props = {ATTR_ZONE_NUMBER: self._zone_number, ATTR_ZONE_SUMMARY: self._summary}
        if self._shade_type:
            props[ATTR_ZONE_SHADE] = self._shade_type
        if self._zone_type:
            props[ATTR_ZONE_TYPE] = self._zone_type
        return props

    def turn_on(self, **kwargs) -> None:
        """Start watering this zone."""
        # Stop other zones first
        self.turn_off()

        # Start this zone
        manual_run_time = timedelta(
            minutes=self._person.config_entry.options.get(
                CONF_MANUAL_RUN_MINS, DEFAULT_MANUAL_RUN_MINS
            )
        )
        self._controller.rachio.zone.start(self.zone_id, manual_run_time.seconds)
        _LOGGER.debug(
            "Watering %s on %s for %s",
            self.name,
            self._controller.name,
            str(manual_run_time),
        )

    def turn_off(self, **kwargs) -> None:
        """Stop watering all zones."""
        self._controller.stop_watering()

    def _poll_update(self, data=None) -> bool:
        """Poll the API to check whether the zone is running."""
        self._current_schedule = self._controller.current_schedule
        return self.zone_id == self._current_schedule.get(KEY_ZONE_ID)

    def _handle_update(self, *args, **kwargs) -> None:
        """Handle incoming webhook zone data."""
        if args[0][KEY_ZONE_ID] != self.zone_id:
            return

        self._summary = kwargs.get(KEY_SUMMARY, str())

        if args[0][KEY_SUBTYPE] == SUBTYPE_ZONE_STARTED:
            self._state = True
        elif args[0][KEY_SUBTYPE] in [SUBTYPE_ZONE_STOPPED, SUBTYPE_ZONE_COMPLETED]:
            self._state = False

        self.schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self._undo_dispatcher = async_dispatcher_connect(
            self.hass, SIGNAL_RACHIO_ZONE_UPDATE, self._handle_update
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe from updates."""
        if self._undo_dispatcher:
            self._undo_dispatcher()


class RachioSchedule(RachioSwitch):
    """Representation of one fixed schedule on the Rachio Iro."""

    def __init__(self, person, controller, data, current_schedule):
        """Initialize a new Rachio Schedule."""
        self._schedule_id = data[KEY_ID]
        self._schedule_name = data[KEY_NAME]
        self._duration = data[KEY_DURATION]
        self._schedule_enabled = data[KEY_ENABLED]
        self._summary = data[KEY_SUMMARY]
        self._current_schedule = current_schedule
        super().__init__(controller, poll=False)
        self._state = self._schedule_id == self._current_schedule.get(KEY_SCHEDULE_ID)
        self._undo_dispatcher = None

    @property
    def name(self) -> str:
        """Return the friendly name of the schedule."""
        return f"{self._schedule_name} Schedule"

    @property
    def unique_id(self) -> str:
        """Return a unique id by combining controller id and schedule."""
        return f"{self._controller.controller_id}-schedule-{self._schedule_id}"

    @property
    def icon(self) -> str:
        """Return the icon to display."""
        return "mdi:water"

    @property
    def device_state_attributes(self) -> dict:
        """Return the optional state attributes."""
        return {
            ATTR_SCHEDULE_SUMMARY: self._summary,
            ATTR_SCHEDULE_ENABLED: self.schedule_is_enabled,
            ATTR_SCHEDULE_DURATION: f"{round(self._duration / 60)} minutes",
        }

    @property
    def schedule_is_enabled(self) -> bool:
        """Return whether the schedule is allowed to run."""
        return self._schedule_enabled

    def turn_on(self, **kwargs) -> None:
        """Start this schedule."""

        self._controller.rachio.schedulerule.start(self._schedule_id)
        _LOGGER.debug(
            "Schedule %s started on %s", self.name, self._controller.name,
        )

    def turn_off(self, **kwargs) -> None:
        """Stop watering all zones."""
        self._controller.stop_watering()

    def _poll_update(self, data=None) -> bool:
        """Poll the API to check whether the schedule is running."""
        self._current_schedule = self._controller.current_schedule
        return self._schedule_id == self._current_schedule.get(KEY_SCHEDULE_ID)

    @callback
    async def _handle_update(self, *args, **kwargs) -> None:
        """Handle incoming webhook schedule data."""
        # Schedule ID not passed when running individual zones, so we catch that error
        try:
            if args[0][KEY_SCHEDULE_ID] == self._schedule_id:
                if args[0][KEY_SUBTYPE] in [SUBTYPE_SCHEDULE_STARTED]:
                    self._state = True
                elif args[0][KEY_SUBTYPE] in [
                    SUBTYPE_SCHEDULE_STOPPED,
                    SUBTYPE_SCHEDULE_COMPLETED,
                ]:
                    self._state = False
        except KeyError:
            pass

        self.schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self._undo_dispatcher = async_dispatcher_connect(
            self.hass, SIGNAL_RACHIO_SCHEDULE_UPDATE, self._handle_update
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe from updates."""
        if self._undo_dispatcher:
            self._undo_dispatcher()
