"""Integration with the Rachio Iro sprinkler system controller."""
from abc import abstractmethod
from contextlib import suppress
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import ATTR_ENTITY_ID, ATTR_ID
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import as_timestamp, now, parse_datetime, utc_from_timestamp

from .const import (
    CONF_MANUAL_RUN_MINS,
    DEFAULT_MANUAL_RUN_MINS,
    DOMAIN as DOMAIN_RACHIO,
    KEY_CUSTOM_CROP,
    KEY_CUSTOM_SHADE,
    KEY_CUSTOM_SLOPE,
    KEY_DEVICE_ID,
    KEY_DURATION,
    KEY_ENABLED,
    KEY_ID,
    KEY_IMAGE_URL,
    KEY_NAME,
    KEY_ON,
    KEY_RAIN_DELAY,
    KEY_RAIN_DELAY_END,
    KEY_SCHEDULE_ID,
    KEY_SUBTYPE,
    KEY_SUMMARY,
    KEY_TYPE,
    KEY_ZONE_ID,
    KEY_ZONE_NUMBER,
    SCHEDULE_TYPE_FIXED,
    SCHEDULE_TYPE_FLEX,
    SERVICE_SET_ZONE_MOISTURE,
    SERVICE_START_MULTIPLE_ZONES,
    SIGNAL_RACHIO_CONTROLLER_UPDATE,
    SIGNAL_RACHIO_RAIN_DELAY_UPDATE,
    SIGNAL_RACHIO_SCHEDULE_UPDATE,
    SIGNAL_RACHIO_ZONE_UPDATE,
    SLOPE_FLAT,
    SLOPE_MODERATE,
    SLOPE_SLIGHT,
    SLOPE_STEEP,
)
from .entity import RachioDevice
from .webhooks import (
    SUBTYPE_RAIN_DELAY_OFF,
    SUBTYPE_RAIN_DELAY_ON,
    SUBTYPE_SCHEDULE_COMPLETED,
    SUBTYPE_SCHEDULE_STARTED,
    SUBTYPE_SCHEDULE_STOPPED,
    SUBTYPE_SLEEP_MODE_OFF,
    SUBTYPE_SLEEP_MODE_ON,
    SUBTYPE_ZONE_COMPLETED,
    SUBTYPE_ZONE_PAUSED,
    SUBTYPE_ZONE_STARTED,
    SUBTYPE_ZONE_STOPPED,
)

_LOGGER = logging.getLogger(__name__)

ATTR_DURATION = "duration"
ATTR_PERCENT = "percent"
ATTR_SCHEDULE_SUMMARY = "Summary"
ATTR_SCHEDULE_ENABLED = "Enabled"
ATTR_SCHEDULE_DURATION = "Duration"
ATTR_SCHEDULE_TYPE = "Type"
ATTR_SORT_ORDER = "sortOrder"
ATTR_ZONE_NUMBER = "Zone number"
ATTR_ZONE_SHADE = "Shade"
ATTR_ZONE_SLOPE = "Slope"
ATTR_ZONE_SUMMARY = "Summary"
ATTR_ZONE_TYPE = "Type"

START_MULTIPLE_ZONES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_DURATION): cv.ensure_list_csv,
    }
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Rachio switches."""
    zone_entities = []
    has_flex_sched = False
    entities = await hass.async_add_executor_job(_create_entities, hass, config_entry)
    for entity in entities:
        if isinstance(entity, RachioZone):
            zone_entities.append(entity)
        if isinstance(entity, RachioSchedule) and entity.type == SCHEDULE_TYPE_FLEX:
            has_flex_sched = True

    async_add_entities(entities)
    _LOGGER.info("%d Rachio switch(es) added", len(entities))

    def start_multiple(service):
        """Service to start multiple zones in sequence."""
        zones_list = []
        person = hass.data[DOMAIN_RACHIO][config_entry.entry_id]
        entity_id = service.data[ATTR_ENTITY_ID]
        duration = iter(service.data[ATTR_DURATION])
        default_time = service.data[ATTR_DURATION][0]
        entity_to_zone_id = {
            entity.entity_id: entity.zone_id for entity in zone_entities
        }

        for (count, data) in enumerate(entity_id):
            if data in entity_to_zone_id:
                # Time can be passed as a list per zone,
                # or one time for all zones
                time = int(next(duration, default_time)) * 60
                zones_list.append(
                    {
                        ATTR_ID: entity_to_zone_id.get(data),
                        ATTR_DURATION: time,
                        ATTR_SORT_ORDER: count,
                    }
                )

        if len(zones_list) != 0:
            person.start_multiple_zones(zones_list)
            _LOGGER.debug("Starting zone(s) %s", entity_id)
        else:
            raise HomeAssistantError("No matching zones found in given entity_ids")

    hass.services.async_register(
        DOMAIN_RACHIO,
        SERVICE_START_MULTIPLE_ZONES,
        start_multiple,
        schema=START_MULTIPLE_ZONES_SCHEMA,
    )

    if has_flex_sched:
        platform = entity_platform.current_platform.get()
        platform.async_register_entity_service(
            SERVICE_SET_ZONE_MOISTURE,
            {vol.Required(ATTR_PERCENT): cv.positive_int},
            "set_moisture_percent",
        )


def _create_entities(hass, config_entry):
    entities = []
    person = hass.data[DOMAIN_RACHIO][config_entry.entry_id]
    # Fetch the schedule once at startup
    # in order to avoid every zone doing it
    for controller in person.controllers:
        entities.append(RachioStandbySwitch(controller))
        entities.append(RachioRainDelay(controller))
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


class RachioSwitch(RachioDevice, SwitchEntity):
    """Represent a Rachio state that can be toggled."""

    def __init__(self, controller):
        """Initialize a new Rachio switch."""
        super().__init__(controller)
        self._state = None

    @property
    def name(self) -> str:
        """Get a name for this switch."""
        return f"Switch on {self._controller.name}"

    @property
    def is_on(self) -> bool:
        """Return whether the switch is currently on."""
        return self._state

    @callback
    def _async_handle_any_update(self, *args, **kwargs) -> None:
        """Determine whether an update event applies to this device."""
        if args[0][KEY_DEVICE_ID] != self._controller.controller_id:
            # For another device
            return

        # For this device
        self._async_handle_update(args, kwargs)

    @abstractmethod
    def _async_handle_update(self, *args, **kwargs) -> None:
        """Handle incoming webhook data."""


class RachioStandbySwitch(RachioSwitch):
    """Representation of a standby status/button."""

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

    @callback
    def _async_handle_update(self, *args, **kwargs) -> None:
        """Update the state using webhook data."""
        if args[0][0][KEY_SUBTYPE] == SUBTYPE_SLEEP_MODE_ON:
            self._state = True
        elif args[0][0][KEY_SUBTYPE] == SUBTYPE_SLEEP_MODE_OFF:
            self._state = False

        self.async_write_ha_state()

    def turn_on(self, **kwargs) -> None:
        """Put the controller in standby mode."""
        self._controller.rachio.device.turn_off(self._controller.controller_id)

    def turn_off(self, **kwargs) -> None:
        """Resume controller functionality."""
        self._controller.rachio.device.turn_on(self._controller.controller_id)

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        if KEY_ON in self._controller.init_data:
            self._state = not self._controller.init_data[KEY_ON]

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_RACHIO_CONTROLLER_UPDATE,
                self._async_handle_any_update,
            )
        )


class RachioRainDelay(RachioSwitch):
    """Representation of a rain delay status/switch."""

    def __init__(self, controller):
        """Set up a Rachio rain delay switch."""
        self._cancel_update = None
        super().__init__(controller)

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return f"{self._controller.name} rain delay"

    @property
    def unique_id(self) -> str:
        """Return a unique id by combining controller id and purpose."""
        return f"{self._controller.controller_id}-delay"

    @property
    def icon(self) -> str:
        """Return an icon for rain delay."""
        return "mdi:camera-timer"

    @callback
    def _async_handle_update(self, *args, **kwargs) -> None:
        """Update the state using webhook data."""
        if self._cancel_update:
            self._cancel_update()
            self._cancel_update = None

        if args[0][0][KEY_SUBTYPE] == SUBTYPE_RAIN_DELAY_ON:
            endtime = parse_datetime(args[0][0][KEY_RAIN_DELAY_END])
            _LOGGER.debug("Rain delay expires at %s", endtime)
            self._state = True
            self._cancel_update = async_track_point_in_utc_time(
                self.hass, self._delay_expiration, endtime
            )
        elif args[0][0][KEY_SUBTYPE] == SUBTYPE_RAIN_DELAY_OFF:
            self._state = False

        self.async_write_ha_state()

    @callback
    def _delay_expiration(self, *args) -> None:
        """Trigger when a rain delay expires."""
        self._state = False
        self._cancel_update = None
        self.async_write_ha_state()

    def turn_on(self, **kwargs) -> None:
        """Activate a 24 hour rain delay on the controller."""
        self._controller.rachio.device.rain_delay(self._controller.controller_id, 86400)
        _LOGGER.debug("Starting rain delay for 24 hours")

    def turn_off(self, **kwargs) -> None:
        """Resume controller functionality."""
        self._controller.rachio.device.rain_delay(self._controller.controller_id, 0)
        _LOGGER.debug("Canceling rain delay")

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        if KEY_RAIN_DELAY in self._controller.init_data:
            self._state = self._controller.init_data[
                KEY_RAIN_DELAY
            ] / 1000 > as_timestamp(now())

        # If the controller was in a rain delay state during a reboot, this re-sets the timer
        if self._state is True:
            delay_end = utc_from_timestamp(
                self._controller.init_data[KEY_RAIN_DELAY] / 1000
            )
            _LOGGER.debug("Re-setting rain delay timer for %s", delay_end)
            self._cancel_update = async_track_point_in_utc_time(
                self.hass, self._delay_expiration, delay_end
            )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_RACHIO_RAIN_DELAY_UPDATE,
                self._async_handle_any_update,
            )
        )


class RachioZone(RachioSwitch):
    """Representation of one zone of sprinklers connected to the Rachio Iro."""

    def __init__(self, person, controller, data, current_schedule):
        """Initialize a new Rachio Zone."""
        self.id = data[KEY_ID]
        self._zone_name = data[KEY_NAME]
        self._zone_number = data[KEY_ZONE_NUMBER]
        self._zone_enabled = data[KEY_ENABLED]
        self._entity_picture = data.get(KEY_IMAGE_URL)
        self._person = person
        self._shade_type = data.get(KEY_CUSTOM_SHADE, {}).get(KEY_NAME)
        self._zone_type = data.get(KEY_CUSTOM_CROP, {}).get(KEY_NAME)
        self._slope_type = data.get(KEY_CUSTOM_SLOPE, {}).get(KEY_NAME)
        self._summary = ""
        self._current_schedule = current_schedule
        super().__init__(controller)

    def __str__(self):
        """Display the zone as a string."""
        return f'Rachio Zone "{self.name}" on {str(self._controller)}'

    @property
    def zone_id(self) -> str:
        """How the Rachio API refers to the zone."""
        return self.id

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
    def extra_state_attributes(self) -> dict:
        """Return the optional state attributes."""
        props = {ATTR_ZONE_NUMBER: self._zone_number, ATTR_ZONE_SUMMARY: self._summary}
        if self._shade_type:
            props[ATTR_ZONE_SHADE] = self._shade_type
        if self._zone_type:
            props[ATTR_ZONE_TYPE] = self._zone_type
        if self._slope_type:
            if self._slope_type == SLOPE_FLAT:
                props[ATTR_ZONE_SLOPE] = "Flat"
            elif self._slope_type == SLOPE_SLIGHT:
                props[ATTR_ZONE_SLOPE] = "Slight"
            elif self._slope_type == SLOPE_MODERATE:
                props[ATTR_ZONE_SLOPE] = "Moderate"
            elif self._slope_type == SLOPE_STEEP:
                props[ATTR_ZONE_SLOPE] = "Steep"
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
        # The API limit is 3 hours, and requires an int be passed
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

    def set_moisture_percent(self, percent) -> None:
        """Set the zone moisture percent."""
        _LOGGER.debug("Setting %s moisture to %s percent", self._zone_name, percent)
        self._controller.rachio.zone.set_moisture_percent(self.id, percent / 100)

    @callback
    def _async_handle_update(self, *args, **kwargs) -> None:
        """Handle incoming webhook zone data."""
        if args[0][KEY_ZONE_ID] != self.zone_id:
            return

        self._summary = args[0][KEY_SUMMARY]

        if args[0][KEY_SUBTYPE] == SUBTYPE_ZONE_STARTED:
            self._state = True
        elif args[0][KEY_SUBTYPE] in [
            SUBTYPE_ZONE_STOPPED,
            SUBTYPE_ZONE_COMPLETED,
            SUBTYPE_ZONE_PAUSED,
        ]:
            self._state = False

        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self._state = self.zone_id == self._current_schedule.get(KEY_ZONE_ID)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_RACHIO_ZONE_UPDATE, self._async_handle_update
            )
        )


class RachioSchedule(RachioSwitch):
    """Representation of one fixed schedule on the Rachio Iro."""

    def __init__(self, person, controller, data, current_schedule):
        """Initialize a new Rachio Schedule."""
        self._schedule_id = data[KEY_ID]
        self._schedule_name = data[KEY_NAME]
        self._duration = data[KEY_DURATION]
        self._schedule_enabled = data[KEY_ENABLED]
        self._summary = data[KEY_SUMMARY]
        self.type = data.get(KEY_TYPE, SCHEDULE_TYPE_FIXED)
        self._current_schedule = current_schedule
        super().__init__(controller)

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
        return "mdi:water" if self.schedule_is_enabled else "mdi:water-off"

    @property
    def extra_state_attributes(self) -> dict:
        """Return the optional state attributes."""
        return {
            ATTR_SCHEDULE_SUMMARY: self._summary,
            ATTR_SCHEDULE_ENABLED: self.schedule_is_enabled,
            ATTR_SCHEDULE_DURATION: f"{round(self._duration / 60)} minutes",
            ATTR_SCHEDULE_TYPE: self.type,
        }

    @property
    def schedule_is_enabled(self) -> bool:
        """Return whether the schedule is allowed to run."""
        return self._schedule_enabled

    def turn_on(self, **kwargs) -> None:
        """Start this schedule."""
        self._controller.rachio.schedulerule.start(self._schedule_id)
        _LOGGER.debug(
            "Schedule %s started on %s",
            self.name,
            self._controller.name,
        )

    def turn_off(self, **kwargs) -> None:
        """Stop watering all zones."""
        self._controller.stop_watering()

    @callback
    def _async_handle_update(self, *args, **kwargs) -> None:
        """Handle incoming webhook schedule data."""
        # Schedule ID not passed when running individual zones, so we catch that error
        with suppress(KeyError):
            if args[0][KEY_SCHEDULE_ID] == self._schedule_id:
                if args[0][KEY_SUBTYPE] in [SUBTYPE_SCHEDULE_STARTED]:
                    self._state = True
                elif args[0][KEY_SUBTYPE] in [
                    SUBTYPE_SCHEDULE_STOPPED,
                    SUBTYPE_SCHEDULE_COMPLETED,
                ]:
                    self._state = False

        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self._state = self._schedule_id == self._current_schedule.get(KEY_SCHEDULE_ID)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_RACHIO_SCHEDULE_UPDATE, self._async_handle_update
            )
        )
