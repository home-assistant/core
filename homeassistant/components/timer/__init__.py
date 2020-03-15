"""Support for Timers."""
from datetime import timedelta
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
ATTR_DURATION = "duration"
ATTR_REMAINING = "remaining"
CONF_DURATION = "duration"

STATUS_IDLE = "idle"
STATUS_ACTIVE = "active"
STATUS_PAUSED = "paused"

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
        return data


class Timer(RestoreEntity):
    """Representation of a timer."""

    def __init__(self, config: typing.Dict):
        """Initialize a timer."""
        self._config = config
        self.editable = True
        self._state = STATUS_IDLE
        self._remaining = config[CONF_DURATION]
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
            ATTR_DURATION: str(self._config[CONF_DURATION]),
            ATTR_EDITABLE: self.editable,
            ATTR_REMAINING: str(self._remaining),
        }

    @property
    def unique_id(self) -> typing.Optional[str]:
        """Return unique id for the entity."""
        return self._config[CONF_ID]

    async def async_added_to_hass(self):
        """Call when entity is about to be added to Home Assistant."""
        # If not None, we got an initial value.
        if self._state is not None:
            return

        state = await self.async_get_last_state()
        self._state = state and state.state == state

    @callback
    def async_start(self, duration):
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
            self.hass, self._async_finished, self._end
        )
        self.async_write_ha_state()

    @callback
    def async_pause(self):
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

    @callback
    def async_cancel(self):
        """Cancel a timer."""
        if self._listener:
            self._listener()
            self._listener = None
        self._state = STATUS_IDLE
        self._end = None
        self._remaining = timedelta()
        self.hass.bus.async_fire(EVENT_TIMER_CANCELLED, {"entity_id": self.entity_id})
        self.async_write_ha_state()

    @callback
    def async_finish(self):
        """Reset and updates the states, fire finished event."""
        if self._state != STATUS_ACTIVE:
            return

        self._listener = None
        self._state = STATUS_IDLE
        self._remaining = timedelta()
        self.hass.bus.async_fire(EVENT_TIMER_FINISHED, {"entity_id": self.entity_id})
        self.async_write_ha_state()

    @callback
    def _async_finished(self, time):
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
