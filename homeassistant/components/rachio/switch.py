"""Integration with the Rachio Iro sprinkler system controller."""

from abc import abstractmethod
from contextlib import suppress
from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_ID
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import as_timestamp, now, parse_datetime, utc_from_timestamp

from .const import (
    CONF_MANUAL_RUN_MINS,
    DEFAULT_MANUAL_RUN_MINS,
    DOMAIN as DOMAIN_RACHIO,
    KEY_CURRENT_STATUS,
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
    KEY_REPORTED_STATE,
    KEY_SCHEDULE_ID,
    KEY_STATE,
    KEY_SUBTYPE,
    KEY_SUMMARY,
    KEY_TYPE,
    KEY_ZONE_ID,
    KEY_ZONE_NUMBER,
    SCHEDULE_TYPE_FIXED,
    SCHEDULE_TYPE_FLEX,
    SERVICE_SET_ZONE_MOISTURE,
    SERVICE_START_MULTIPLE_ZONES,
    SERVICE_START_WATERING,
    SIGNAL_RACHIO_CONTROLLER_UPDATE,
    SIGNAL_RACHIO_RAIN_DELAY_UPDATE,
    SIGNAL_RACHIO_SCHEDULE_UPDATE,
    SIGNAL_RACHIO_ZONE_UPDATE,
    SLOPE_FLAT,
    SLOPE_MODERATE,
    SLOPE_SLIGHT,
    SLOPE_STEEP,
)
from .device import RachioPerson
from .entity import RachioDevice, RachioHoseTimerEntity
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
ATTR_WATERING_DURATION = "Watering Duration seconds"
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
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

    def start_multiple(service: ServiceCall) -> None:
        """Service to start multiple zones in sequence."""
        zones_list = []
        person = hass.data[DOMAIN_RACHIO][config_entry.entry_id]
        entity_id = service.data[ATTR_ENTITY_ID]
        duration = iter(service.data[ATTR_DURATION])
        default_time = service.data[ATTR_DURATION][0]
        entity_to_zone_id = {
            entity.entity_id: entity.zone_id for entity in zone_entities
        }

        for count, data in enumerate(entity_id):
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

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_START_WATERING,
        {
            vol.Optional(ATTR_DURATION): cv.positive_int,
        },
        "turn_on",
    )

    # If only hose timers on account, none of these services apply
    if not zone_entities:
        return

    hass.services.async_register(
        DOMAIN_RACHIO,
        SERVICE_START_MULTIPLE_ZONES,
        start_multiple,
        schema=START_MULTIPLE_ZONES_SCHEMA,
    )

    if has_flex_sched:
        platform = entity_platform.async_get_current_platform()
        platform.async_register_entity_service(
            SERVICE_SET_ZONE_MOISTURE,
            {vol.Required(ATTR_PERCENT): cv.positive_int},
            "set_moisture_percent",
        )


def _create_entities(hass: HomeAssistant, config_entry: ConfigEntry) -> list[Entity]:
    entities: list[Entity] = []
    person: RachioPerson = hass.data[DOMAIN_RACHIO][config_entry.entry_id]
    # Fetch the schedule once at startup
    # in order to avoid every zone doing it
    for controller in person.controllers:
        entities.append(RachioStandbySwitch(controller))
        entities.append(RachioRainDelay(controller))
        zones = controller.list_zones()
        schedules = controller.list_schedules()
        flex_schedules = controller.list_flex_schedules()
        current_schedule = controller.current_schedule
        entities.extend(
            RachioZone(person, controller, zone, current_schedule) for zone in zones
        )
        entities.extend(
            RachioSchedule(person, controller, schedule, current_schedule)
            for schedule in schedules + flex_schedules
        )
    entities.extend(
        RachioValve(person, base_station, valve, base_station.coordinator)
        for base_station in person.base_stations
        for valve in base_station.coordinator.data.values()
    )
    return entities


class RachioSwitch(RachioDevice, SwitchEntity):
    """Represent a Rachio state that can be toggled."""

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

    _attr_has_entity_name = True
    _attr_translation_key = "standby"

    @property
    def unique_id(self) -> str:
        """Return a unique id by combining controller id and purpose."""
        return f"{self._controller.controller_id}-standby"

    @callback
    def _async_handle_update(self, *args, **kwargs) -> None:
        """Update the state using webhook data."""
        if args[0][0][KEY_SUBTYPE] == SUBTYPE_SLEEP_MODE_ON:
            self._attr_is_on = True
        elif args[0][0][KEY_SUBTYPE] == SUBTYPE_SLEEP_MODE_OFF:
            self._attr_is_on = False

        self.async_write_ha_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Put the controller in standby mode."""
        self._controller.rachio.device.turn_off(self._controller.controller_id)

    def turn_off(self, **kwargs: Any) -> None:
        """Resume controller functionality."""
        self._controller.rachio.device.turn_on(self._controller.controller_id)

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        if KEY_ON in self._controller.init_data:
            self._attr_is_on = not self._controller.init_data[KEY_ON]

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_RACHIO_CONTROLLER_UPDATE,
                self._async_handle_any_update,
            )
        )


class RachioRainDelay(RachioSwitch):
    """Representation of a rain delay status/switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "rain_delay"

    def __init__(self, controller) -> None:
        """Set up a Rachio rain delay switch."""
        self._cancel_update: CALLBACK_TYPE | None = None
        super().__init__(controller)

    @property
    def unique_id(self) -> str:
        """Return a unique id by combining controller id and purpose."""
        return f"{self._controller.controller_id}-delay"

    @callback
    def _async_handle_update(self, *args, **kwargs) -> None:
        """Update the state using webhook data."""
        if self._cancel_update:
            self._cancel_update()
            self._cancel_update = None

        if args[0][0][KEY_SUBTYPE] == SUBTYPE_RAIN_DELAY_ON:
            endtime = parse_datetime(args[0][0][KEY_RAIN_DELAY_END])
            _LOGGER.debug("Rain delay expires at %s", endtime)
            self._attr_is_on = True
            assert endtime is not None
            self._cancel_update = async_track_point_in_utc_time(
                self.hass, self._delay_expiration, endtime
            )
        elif args[0][0][KEY_SUBTYPE] == SUBTYPE_RAIN_DELAY_OFF:
            self._attr_is_on = False

        self.async_write_ha_state()

    @callback
    def _delay_expiration(self, *args) -> None:
        """Trigger when a rain delay expires."""
        self._attr_is_on = False
        self._cancel_update = None
        self.async_write_ha_state()

    def turn_on(self, **kwargs: Any) -> None:
        """Activate a 24 hour rain delay on the controller."""
        self._controller.rachio.device.rain_delay(self._controller.controller_id, 86400)
        _LOGGER.debug("Starting rain delay for 24 hours")

    def turn_off(self, **kwargs: Any) -> None:
        """Resume controller functionality."""
        self._controller.rachio.device.rain_delay(self._controller.controller_id, 0)
        _LOGGER.debug("Canceling rain delay")

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        if KEY_RAIN_DELAY in self._controller.init_data:
            self._attr_is_on = self._controller.init_data[
                KEY_RAIN_DELAY
            ] / 1000 > as_timestamp(now())

        # If the controller was in a rain delay state during a reboot, this re-sets the timer
        if self._attr_is_on is True:
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

    _attr_icon = "mdi:water"

    def __init__(self, person, controller, data, current_schedule) -> None:
        """Initialize a new Rachio Zone."""
        self.id = data[KEY_ID]
        self._attr_name = data[KEY_NAME]
        self._zone_number = data[KEY_ZONE_NUMBER]
        self._zone_enabled = data[KEY_ENABLED]
        self._attr_entity_picture = data.get(KEY_IMAGE_URL)
        self._person = person
        self._shade_type = data.get(KEY_CUSTOM_SHADE, {}).get(KEY_NAME)
        self._zone_type = data.get(KEY_CUSTOM_CROP, {}).get(KEY_NAME)
        self._slope_type = data.get(KEY_CUSTOM_SLOPE, {}).get(KEY_NAME)
        self._summary = ""
        self._current_schedule = current_schedule
        self._attr_unique_id = f"{controller.controller_id}-zone-{self.id}"
        super().__init__(controller)

    def __str__(self):
        """Display the zone as a string."""
        return f'Rachio Zone "{self.name}" on {str(self._controller)}'

    @property
    def zone_id(self) -> str:
        """How the Rachio API refers to the zone."""
        return self.id

    @property
    def zone_is_enabled(self) -> bool:
        """Return whether the zone is allowed to run."""
        return self._zone_enabled

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
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

    def turn_on(self, **kwargs: Any) -> None:
        """Start watering this zone."""
        # Stop other zones first
        self.turn_off()

        # Start this zone
        if ATTR_DURATION in kwargs:
            manual_run_time = timedelta(minutes=kwargs[ATTR_DURATION])
        else:
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

    def turn_off(self, **kwargs: Any) -> None:
        """Stop watering all zones."""
        self._controller.stop_watering()

    def set_moisture_percent(self, percent) -> None:
        """Set the zone moisture percent."""
        _LOGGER.debug("Setting %s moisture to %s percent", self.name, percent)
        self._controller.rachio.zone.set_moisture_percent(self.id, percent / 100)

    @callback
    def _async_handle_update(self, *args, **kwargs) -> None:
        """Handle incoming webhook zone data."""
        if args[0][KEY_ZONE_ID] != self.zone_id:
            return

        self._summary = args[0][KEY_SUMMARY]

        if args[0][KEY_SUBTYPE] == SUBTYPE_ZONE_STARTED:
            self._attr_is_on = True
        elif args[0][KEY_SUBTYPE] in [
            SUBTYPE_ZONE_STOPPED,
            SUBTYPE_ZONE_COMPLETED,
            SUBTYPE_ZONE_PAUSED,
        ]:
            self._attr_is_on = False

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self._attr_is_on = self.zone_id == self._current_schedule.get(KEY_ZONE_ID)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_RACHIO_ZONE_UPDATE, self._async_handle_update
            )
        )


class RachioSchedule(RachioSwitch):
    """Representation of one fixed schedule on the Rachio Iro."""

    def __init__(self, person, controller, data, current_schedule) -> None:
        """Initialize a new Rachio Schedule."""
        self._schedule_id = data[KEY_ID]
        self._duration = data[KEY_DURATION]
        self._schedule_enabled = data[KEY_ENABLED]
        self._summary = data[KEY_SUMMARY]
        self.type = data.get(KEY_TYPE, SCHEDULE_TYPE_FIXED)
        self._current_schedule = current_schedule
        self._attr_unique_id = (
            f"{controller.controller_id}-schedule-{self._schedule_id}"
        )
        self._attr_name = f"{data[KEY_NAME]} Schedule"
        super().__init__(controller)

    @property
    def icon(self) -> str:
        """Return the icon to display."""
        return "mdi:water" if self.schedule_is_enabled else "mdi:water-off"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
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

    def turn_on(self, **kwargs: Any) -> None:
        """Start this schedule."""
        self._controller.rachio.schedulerule.start(self._schedule_id)
        _LOGGER.debug(
            "Schedule %s started on %s",
            self.name,
            self._controller.name,
        )

    def turn_off(self, **kwargs: Any) -> None:
        """Stop watering all zones."""
        self._controller.stop_watering()

    @callback
    def _async_handle_update(self, *args, **kwargs) -> None:
        """Handle incoming webhook schedule data."""
        # Schedule ID not passed when running individual zones, so we catch that error
        with suppress(KeyError):
            if args[0][KEY_SCHEDULE_ID] == self._schedule_id:
                if args[0][KEY_SUBTYPE] in [SUBTYPE_SCHEDULE_STARTED]:
                    self._attr_is_on = True
                elif args[0][KEY_SUBTYPE] in [
                    SUBTYPE_SCHEDULE_STOPPED,
                    SUBTYPE_SCHEDULE_COMPLETED,
                ]:
                    self._attr_is_on = False

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self._attr_is_on = self._schedule_id == self._current_schedule.get(
            KEY_SCHEDULE_ID
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_RACHIO_SCHEDULE_UPDATE, self._async_handle_update
            )
        )


class RachioValve(RachioHoseTimerEntity, SwitchEntity):
    """Representation of one smart hose timer valve."""

    _attr_name = None

    def __init__(self, person, base, data, coordinator) -> None:
        """Initialize a new smart hose valve."""
        super().__init__(data, coordinator)
        self._person = person
        self._base = base
        self._attr_unique_id = f"{self.id}-valve"

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on this valve."""
        if ATTR_DURATION in kwargs:
            manual_run_time = timedelta(minutes=kwargs[ATTR_DURATION])
        else:
            manual_run_time = timedelta(
                minutes=self._person.config_entry.options.get(
                    CONF_MANUAL_RUN_MINS, DEFAULT_MANUAL_RUN_MINS
                )
            )

        self._base.start_watering(self.id, manual_run_time.seconds)
        self._attr_is_on = True
        self.schedule_update_ha_state(force_refresh=True)
        _LOGGER.debug("Starting valve %s for %s", self._name, str(manual_run_time))

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off this valve."""
        self._base.stop_watering(self.id)
        self._attr_is_on = False
        self.schedule_update_ha_state(force_refresh=True)
        _LOGGER.debug("Stopping watering on valve %s", self._name)

    @callback
    def _update_attr(self) -> None:
        """Handle updated coordinator data."""
        data = self.coordinator.data[self.id]

        self._static_attrs = data[KEY_STATE][KEY_REPORTED_STATE]
        self._attr_is_on = KEY_CURRENT_STATUS in self._static_attrs
