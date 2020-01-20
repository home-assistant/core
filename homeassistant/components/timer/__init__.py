"""Support for Timers."""
from datetime import timedelta, datetime, timezone
import logging
import typing

import voluptuous as vol

from homeassistant.const import (
    ATTR_EDITABLE,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    SERVICE_RELOAD,
)
from homeassistant.core import callback
from homeassistant.helpers import collection
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.helpers.service
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, HomeAssistantType, ServiceCallType
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = "timer"
ENTITY_ID_FORMAT = DOMAIN + ".{}"

DEFAULT_DURATION = 0
DEFAULT_RESTORE = False
DEFAULT_RESTORE_GRACE_PERIOD = timedelta(minutes=15)
ATTR_DURATION = "duration"
ATTR_REMAINING = "remaining"
ATTR_RESTORE = "restore"
ATTR_RESTORE_GRACE_PERIOD = "restore_grace_period"
ATTR_END = "end"
CONF_DURATION = "duration"
CONF_RESTORE = "restore"
CONF_RESTORE_GRACE_PERIOD = "restore_grace_period"

STATUS_IDLE = "idle"
STATUS_ACTIVE = "active"
STATUS_PAUSED = "paused"

VIABLE_STATUSES = [STATUS_IDLE, STATUS_ACTIVE, STATUS_PAUSED ]

EVENT_TIMER_FINISHED = "timer.finished"
EVENT_TIMER_CANCELLED = "timer.cancelled"
EVENT_TIMER_STARTED = "timer.started"
EVENT_TIMER_RESTARTED = "timer.restarted"
EVENT_TIMER_PAUSED = "timer.paused"

SERVICE_START = "start"
SERVICE_PAUSE = "pause"
SERVICE_CANCEL = "cancel"
SERVICE_FINISH = "finish"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

CREATE_FIELDS = {
    vol.Required(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_DURATION, default=DEFAULT_DURATION): cv.time_period,
}
UPDATE_FIELDS = {
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_DURATION): cv.time_period,
}


def _none_to_empty_dict(value):
    if value is None:
        return {}
    return value

def _time_str(time_value):
    time_value = str(time_value)
    if "day" in time_value:
        part0 = str(time_value).split(",")
        part1 = str(part0[0]).split(" ")
        part0[0] = int(part1[0]) * 24
        times = part0[1].split(":")
        hour = part0[0] + int(times[0])
        time_value = "{:02}:{:02}:{:02}".format(int(hour),int(times[1]),int(times[2]))
    return time_value

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            vol.All(
                _none_to_empty_dict,
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_ICON): cv.icon,
                    vol.Optional(
                        CONF_DURATION, default=DEFAULT_DURATION
                    ): cv.time_period,
                    vol.Optional(
                        CONF_RESTORE, default=DEFAULT_RESTORE
                    ): cv.boolean,
                    vol.Optional(
                        CONF_RESTORE_GRACE_PERIOD, default=DEFAULT_RESTORE_GRACE_PERIOD
                    ): cv.time_period,
                },
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)

RELOAD_SERVICE_SCHEMA = vol.Schema({})


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up an input select."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.attach_entity_component_collection(
        component, yaml_collection, Timer.from_yaml
    )

    storage_collection = TimerStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        logging.getLogger(f"{__name__}.storage_collection"),
        id_manager,
    )
    collection.attach_entity_component_collection(component, storage_collection, Timer)

    await yaml_collection.async_load(
        [{CONF_ID: id_, **cfg} for id_, cfg in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.StorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

    collection.attach_entity_registry_cleaner(hass, DOMAIN, DOMAIN, yaml_collection)
    collection.attach_entity_registry_cleaner(hass, DOMAIN, DOMAIN, storage_collection)

    async def reload_service_handler(service_call: ServiceCallType) -> None:
        """Reload yaml entities."""
        conf = await component.async_prepare_reload(skip_reset=True)
        if conf is None:
            conf = {DOMAIN: {}}
        await yaml_collection.async_load(
            [{CONF_ID: id_, **cfg} for id_, cfg in conf.get(DOMAIN, {}).items()]
        )

    homeassistant.helpers.service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler,
        schema=RELOAD_SERVICE_SCHEMA,
    )
    component.async_register_entity_service(
        SERVICE_START,
        {vol.Optional(ATTR_DURATION, default=DEFAULT_DURATION): cv.time_period},
        "async_start",
    )
    component.async_register_entity_service(SERVICE_PAUSE, {}, "async_pause")
    component.async_register_entity_service(SERVICE_CANCEL, {}, "async_cancel")
    component.async_register_entity_service(SERVICE_FINISH, {}, "async_finish")

    return True


class TimerStorageCollection(collection.StorageCollection):
    """Timer storage based collection."""

    CREATE_SCHEMA = vol.Schema(CREATE_FIELDS)
    UPDATE_SCHEMA = vol.Schema(UPDATE_FIELDS)

    async def _process_create_data(self, data: typing.Dict) -> typing.Dict:
        """Validate the config is valid."""
        data = self.CREATE_SCHEMA(data)
        # make duration JSON serializeable
        data[CONF_DURATION] = str(data[CONF_DURATION])
        data[CONF_RESTORE] = str(data[CONF_RESTORE])
        data[CONF_RESTORE_GRACE_PERIOD] = str(data[CONF_RESTORE_GRACE_PERIOD])
        return data

    @callback
    def _get_suggested_id(self, info: typing.Dict) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]

    async def _update_data(self, data: dict, update_data: typing.Dict) -> typing.Dict:
        """Return a new updated data object."""
        data = {**data, **self.UPDATE_SCHEMA(update_data)}
        # make duration JSON serializeable
        data[CONF_DURATION] = str(data[CONF_DURATION])
        data[CONF_RESTORE] = str(data[CONF_RESTORE])
        data[CONF_RESTORE_GRACE_PERIOD] = str(data[CONF_RESTORE_GRACE_PERIOD])
        return data


class Timer(RestoreEntity):
    """Representation of a timer."""

    def __init__(self, config: typing.Dict):
        """Initialize a timer."""
        self._config = config
        self.editable = True
        self._state = STATUS_IDLE
        self._remaining = config[CONF_DURATION]
        self._restore = config[CONF_RESTORE] if config[CONF_RESTORE] is not None \
                        else DEFAULT_RESTORE
        if self._restore:
            self._restore_grace_period = config[CONF_RESTORE_GRACE_PERIOD] \
                                    if config[CONF_RESTORE_GRACE_PERIOD] is not None \
                                    else DEFAULT_RESTORE_GRACE_PERIOD
        else:
            self._restore_grace_period = None
        
        self._end = None
        self._listener = None

    @classmethod
    def from_yaml(cls, config: typing.Dict) -> "Timer":
        """Return entity instance initialized from yaml storage."""
        timer = cls(config)
        timer.entity_id = ENTITY_ID_FORMAT.format(config[CONF_ID])
        timer.editable = False
        return timer

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return name of the timer."""
        return self._config.get(CONF_NAME)

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    def state(self):
        """Return the current value of the timer."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_DURATION: _time_str(self._config[CONF_DURATION]),
            ATTR_EDITABLE: self.editable,
            ATTR_REMAINING: _time_str(self._remaining),
            ATTR_RESTORE: str(self._restore),
            ATTR_RESTORE_GRACE_PERIOD: str(self._restore_grace_period),
            ATTR_END: str(self._end.replace(tzinfo=timezone.utc).astimezone(tz=None)) \
                      if self._end is not None \
                      else None,
        }

    @property
    def unique_id(self) -> typing.Optional[str]:
        """Return unique id for the entity."""
        return self._config[CONF_ID]

    async def async_added_to_hass(self):
        """Call when entity is about to be added to Home Assistant."""
        if not self._restore:
            self._state = STATUS_IDLE
            return
        
        # Check for previous recorded state
        state = await self.async_get_last_state()
        if state is not None:
            for check_status in VIABLE_STATUSES:
                if state.state == check_status:
                    self._state = state.state
                    # restore last duration if config doesn't have a default
                    if not self._config[CONF_DURATION] and not state.attributes.get(ATTR_DURATION) == "None":
                        try:
                            duration_data = list(map(int, str(state.attributes.get(ATTR_DURATION)).split(":")))
                            self._config[CONF_DURATION] = timedelta(hours=duration_data[0], 
                                                                    minutes=duration_data[1], 
                                                                    seconds=duration_data[2])
                        except:
                            break
                    # restore remaining (needed for paused state)
                    if self._state == STATUS_PAUSED \
                       and not state.attributes.get(ATTR_REMAINING) == "None" \
                       and not state.attributes.get(ATTR_REMAINING) == str(timedelta()):
                        try:
                            remaining_dt = list(map(int, str(state.attributes.get(ATTR_REMAINING)).split(":")))
                            self._remaining = timedelta(hours=remaining_dt[0],
                                                        minutes=remaining_dt[1],
                                                        seconds=remaining_dt[2])
                        except:
                            break
                    else:
                        self._remaining = timedelta()
                    try:
                        self._end = datetime.strptime(state.attributes.get(ATTR_END), "%Y-%m-%d %H:%M:%S%z") \
                                    if not state.attributes.get(ATTR_END) == "None" \
                                       and state.attributes.get(ATTR_END) is not None \
                                    else None
                    except:
                        break
                    if self._state == STATUS_ACTIVE:
                        try:
                            self._remaining = self._end - dt_util.utcnow().replace(microsecond=0)
                            # Only restore if restore_grace_period not exceeded
                            if self._remaining + self._restore_grace_period >= timedelta():
                                self._state = STATUS_PAUSED
                                self._end = None
                                await self.async_start(None)
                            else:
                                self._state = STATUS_IDLE
                        except:
                            break
                    return
        # Set state to IDLE if no recorded state, or invalid
        self._state = STATUS_IDLE

    async def async_start(self, duration):
        """Start a timer."""
        if self._listener:
            self._listener()
            self._listener = None
        newduration = None
        if duration:
            newduration = duration

        event = EVENT_TIMER_STARTED
        if self._state == STATUS_ACTIVE or self._state == STATUS_PAUSED:
            event = EVENT_TIMER_RESTARTED

        self._state = STATUS_ACTIVE
        start = dt_util.utcnow().replace(microsecond=0)
        if self._remaining and newduration is None:
            self._end = start + self._remaining
        else:
            if newduration:
                self._config[CONF_DURATION] = newduration
                self._remaining = newduration
            else:
                self._remaining = self._config[CONF_DURATION]
            self._end = start + self._config[CONF_DURATION]

        self.hass.bus.async_fire(event, {"entity_id": self.entity_id})

        self._listener = async_track_point_in_utc_time(
            self.hass, self.async_finished, self._end
        )
        self.async_write_ha_state()

    async def async_pause(self):
        """Pause a timer."""
        if self._listener is None:
            return

        self._listener()
        self._listener = None
        self._remaining = self._end - dt_util.utcnow().replace(microsecond=0)
        self._state = STATUS_PAUSED
        self._end = None
        self.hass.bus.async_fire(EVENT_TIMER_PAUSED, {"entity_id": self.entity_id})
        self.async_write_ha_state()

    async def async_cancel(self):
        """Cancel a timer."""
        if self._listener:
            self._listener()
            self._listener = None
        self._state = STATUS_IDLE
        self._end = None
        self._remaining = timedelta()
        self.hass.bus.async_fire(EVENT_TIMER_CANCELLED, {"entity_id": self.entity_id})
        self.async_write_ha_state()

    async def async_finish(self):
        """Reset and updates the states, fire finished event."""
        if self._state != STATUS_ACTIVE:
            return

        self._listener = None
        self._state = STATUS_IDLE
        self._remaining = timedelta()
        self.hass.bus.async_fire(EVENT_TIMER_FINISHED, {"entity_id": self.entity_id})
        self.async_write_ha_state()

    async def async_finished(self, time):
        """Reset and updates the states, fire finished event."""
        if self._state != STATUS_ACTIVE:
            return

        self._listener = None
        self._state = STATUS_IDLE
        self._remaining = timedelta()
        self.hass.bus.async_fire(EVENT_TIMER_FINISHED, {"entity_id": self.entity_id})
        self.async_write_ha_state()

    async def async_update_config(self, config: typing.Dict) -> None:
        """Handle when the config is updated."""
        self._config = config
        self.async_write_ha_state()
