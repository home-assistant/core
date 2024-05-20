"""The Alarm Clock integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta
import logging
from typing import Any, Self

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_ENTITY_ID,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    SERVICE_RELOAD,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    WEEKDAYS,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import collection, service
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_ALARM_TIME,
    ATTR_NEXT_ALARM,
    ATTR_REPEAT_DAYS,
    CONF_ALARM_TIME,
    CONF_REPEAT_DAYS,
    DOMAIN,
    ENTITY_ID_FORMAT,
    EVENT_ALARM_CLOCK_CANCELLED,
    EVENT_ALARM_CLOCK_CHANGED,
    EVENT_ALARM_CLOCK_FINISHED,
    EVENT_ALARM_CLOCK_STARTED,
    STORAGE_FIELDS,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


def _format_time(time_obj):
    return time_obj.strftime("%H:%M:%S")


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            vol.All(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_ICON): cv.icon,
                    vol.Required(CONF_ALARM_TIME): vol.All(cv.time, _format_time),
                    vol.Optional(CONF_REPEAT_DAYS, default=[]): cv.weekdays,
                },
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)

RELOAD_SERVICE_SCHEMA = vol.Schema({})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an alarm clock."""
    component = EntityComponent[AlarmClock](_LOGGER, DOMAIN, hass)
    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, AlarmClock
    )

    storage_collection = AlarmClockStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, AlarmClock
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **cfg} for id_, cfg in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.DictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, STORAGE_FIELDS, STORAGE_FIELDS
    ).async_setup(hass)

    async def reload_service_handler(service_call: ServiceCall) -> None:
        """Reload yaml entities."""
        conf = await component.async_prepare_reload(skip_reset=True)
        if conf is None:
            conf = {DOMAIN: {}}
        await yaml_collection.async_load(
            [{CONF_ID: id_, **cfg} for id_, cfg in conf.get(DOMAIN, {}).items()]
        )

    service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler,
        schema=RELOAD_SERVICE_SCHEMA,
    )
    component.async_register_entity_service(
        SERVICE_TURN_ON,
        {vol.Optional(ATTR_ALARM_TIME): cv.time},
        "async_turn_on",
    )
    component.async_register_entity_service(SERVICE_TURN_OFF, {}, "async_turn_off")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, (Platform.SENSOR,)
    ):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class AlarmClock(collection.CollectionEntity, RestoreEntity):
    """Representation of an alarm clock."""

    editable: bool

    def __init__(self, config: ConfigType) -> None:
        """Initialize a timer."""
        self._config: dict = config
        self._state = STATE_OFF
        self._alarm_time = cv.time(self._config[CONF_ALARM_TIME])
        self._repeat_days = self._config.get(CONF_REPEAT_DAYS, [])
        self._next_alarm = None
        self._listener: Callable[[], None] | None = None

        self._attr_should_poll = False
        self._attr_force_update = True

    @classmethod
    def from_storage(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from storage."""
        timer = cls(config)
        timer.editable = True
        return timer

    @classmethod
    def from_yaml(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from yaml."""
        timer = cls(config)
        timer.entity_id = ENTITY_ID_FORMAT.format(config[CONF_ID])
        timer.editable = False
        return timer

    @property
    def name(self) -> str | None:
        """Return name of the timer."""
        return self._config.get(CONF_NAME)

    @property
    def icon(self) -> str | None:
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    def state(self) -> str:
        """Return the current state of the alarm clock."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs: dict[str, Any] = {
            ATTR_ALARM_TIME: self._alarm_time,
            ATTR_EDITABLE: self.editable,
        }

        if self._repeat_days is not None:
            attrs[ATTR_REPEAT_DAYS] = self._repeat_days

        if self._next_alarm is not None:
            attrs[ATTR_NEXT_ALARM] = self._next_alarm.isoformat()

        return attrs

    @property
    def unique_id(self) -> str | None:
        """Return unique id for the entity."""
        return self._config[CONF_ID]  # type: ignore[no-any-return]

    async def async_added_to_hass(self) -> None:
        """Call when entity is about to be added to Home Assistant."""
        # If no previous state exists, start with off
        if (state := await self.async_get_last_state()) is None:
            self._state = STATE_OFF
            return

        # Begin restoring state
        self._state = state.state

        # Nothing more to do if the alarm is off
        if self._state == STATE_OFF:
            return

        self._next_alarm = cv.datetime(state.attributes[ATTR_NEXT_ALARM])

        # If the alarm ended before now, finish it.
        # The event will indicate when the alarm was expected to fire.
        if (
            self._next_alarm - dt_util.utcnow().replace(microsecond=0) <= timedelta(0)
            and not self._repeat_days
        ):
            self._async_finish()
        else:
            self.async_turn_on()

    @callback
    def async_turn_on(self, alarm_time: time | None = None) -> None:
        """Turn on an alarm clock."""
        if self._listener:
            self._listener()
            self._listener = None

        if alarm_time:
            self._alarm_time = alarm_time

        event = (
            EVENT_ALARM_CLOCK_STARTED
            if self._state == STATE_OFF
            else EVENT_ALARM_CLOCK_CHANGED
        )

        self._state = STATE_ON

        now = dt_util.utcnow().replace(microsecond=0)

        # Set the alarm to the next valid date in the future
        alarm_time_delta = timedelta(
            hours=self._alarm_time.hour,
            minutes=self._alarm_time.minute,
            seconds=self._alarm_time.second,
        )
        self._next_alarm = dt_util.start_of_local_day(now) + alarm_time_delta
        if self._next_alarm <= now:
            self._next_alarm += timedelta(days=1)

        if self._repeat_days:
            # Map days of the week from strings to integers that match datetime
            day_indexes = {day: i for i, day in enumerate(WEEKDAYS)}
            repeat_day_indexes = [day_indexes[day] for day in self._repeat_days]

            # Increment the date until we find one that matches the repeat days
            while self._next_alarm.weekday() not in repeat_day_indexes:
                self._next_alarm += timedelta(days=1)

        self.async_write_ha_state()
        self.hass.bus.async_fire(event, {ATTR_ENTITY_ID: self.entity_id})

        self._listener = async_track_point_in_time(
            self.hass, self._async_finish, self._next_alarm
        )

    @callback
    def async_turn_off(self) -> None:
        """Turn off an alarm clock."""
        if self._listener:
            self._listener()
            self._listener = None

        self._state = STATE_OFF
        self._next_alarm = None
        self.async_write_ha_state()
        self.hass.bus.async_fire(
            EVENT_ALARM_CLOCK_CANCELLED, {ATTR_ENTITY_ID: self.entity_id}
        )

    @callback
    def _async_finish(self, _: datetime | None = None) -> None:
        """Reset and updates the states, fire finished event."""
        if not self._repeat_days:
            if self._listener:
                self._listener()
                self._listener = None

            self._state = STATE_OFF
            self._next_alarm = None
            self.async_write_ha_state()
            self.hass.bus.async_fire(
                EVENT_ALARM_CLOCK_FINISHED, {ATTR_ENTITY_ID: self.entity_id}
            )
        else:
            self.async_turn_on()

    async def async_update_config(self, config: ConfigType) -> None:
        """Handle config updates."""
        self._config = config
        self._alarm_time = cv.time(self._config[CONF_ALARM_TIME])
        self._repeat_days = self._config.get(CONF_REPEAT_DAYS, [])

        if self._state == STATE_ON:
            self.async_turn_on()
        else:
            self.async_write_ha_state()


class AlarmClockStorageCollection(collection.DictStorageCollection):
    """Alarm Clock storage collection."""

    CREATE_UPDATE_SCHEMA = vol.Schema(STORAGE_FIELDS)

    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        data = self.CREATE_UPDATE_SCHEMA(data)
        # make alarm_time JSON serializeable
        data[CONF_ALARM_TIME] = _format_time(data[CONF_ALARM_TIME])
        return data

    @callback
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]  # type: ignore[no-any-return]

    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        data = {CONF_ID: item[CONF_ID]} | self.CREATE_UPDATE_SCHEMA(update_data)
        # make alarm_time JSON serializeable
        if CONF_ALARM_TIME in update_data:
            data[CONF_ALARM_TIME] = _format_time(data[CONF_ALARM_TIME])
        return data  # type: ignore[no-any-return]
