"""Support to select a date and/or a time."""

from __future__ import annotations

import datetime as py_datetime
import logging
from typing import Any, Self

import voluptuous as vol

from homeassistant.const import (
    ATTR_DATE,
    ATTR_EDITABLE,
    ATTR_TIME,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import collection, config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.helpers.service
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = "input_datetime"

CONF_HAS_DATE = "has_date"
CONF_HAS_TIME = "has_time"
CONF_INITIAL = "initial"

DEFAULT_TIME = py_datetime.time(0, 0, 0)

ATTR_DATETIME = "datetime"
ATTR_TIMESTAMP = "timestamp"

FMT_DATE = "%Y-%m-%d"
FMT_TIME = "%H:%M:%S"
FMT_DATETIME = f"{FMT_DATE} {FMT_TIME}"


def validate_set_datetime_attrs(config):
    """Validate set_datetime service attributes."""
    has_date_or_time_attr = any(key in config for key in (ATTR_DATE, ATTR_TIME))
    if (
        sum([has_date_or_time_attr, ATTR_DATETIME in config, ATTR_TIMESTAMP in config])
        > 1
    ):
        raise vol.Invalid(f"Cannot use together: {', '.join(config.keys())}")
    return config


STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

STORAGE_FIELDS: VolDictType = {
    vol.Required(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional(CONF_HAS_DATE, default=False): cv.boolean,
    vol.Optional(CONF_HAS_TIME, default=False): cv.boolean,
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_INITIAL): cv.string,
}


def has_date_or_time(conf):
    """Check at least date or time is true."""
    if conf[CONF_HAS_DATE] or conf[CONF_HAS_TIME]:
        return conf

    raise vol.Invalid("Entity needs at least a date or a time")


def valid_initial(conf: dict[str, Any]) -> dict[str, Any]:
    """Check the initial value is valid."""
    if not (conf.get(CONF_INITIAL)):
        return conf

    # Ensure we can parse the initial value, raise vol.Invalid on failure
    parse_initial_datetime(conf)
    return conf


def parse_initial_datetime(conf: dict[str, Any]) -> py_datetime.datetime:
    """Check the initial value is valid."""
    initial: str = conf[CONF_INITIAL]

    if conf[CONF_HAS_DATE] and conf[CONF_HAS_TIME]:
        if (datetime := dt_util.parse_datetime(initial)) is not None:
            return datetime
        raise vol.Invalid(f"Initial value '{initial}' can't be parsed as a datetime")

    if conf[CONF_HAS_DATE]:
        if (date := dt_util.parse_date(initial)) is not None:
            return py_datetime.datetime.combine(date, DEFAULT_TIME)
        raise vol.Invalid(f"Initial value '{initial}' can't be parsed as a date")

    if (time := dt_util.parse_time(initial)) is not None:
        return py_datetime.datetime.combine(py_datetime.date.today(), time)
    raise vol.Invalid(f"Initial value '{initial}' can't be parsed as a time")


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            vol.All(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_HAS_DATE, default=False): cv.boolean,
                    vol.Optional(CONF_HAS_TIME, default=False): cv.boolean,
                    vol.Optional(CONF_ICON): cv.icon,
                    vol.Optional(CONF_INITIAL): cv.string,
                },
                has_date_or_time,
                valid_initial,
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)
RELOAD_SERVICE_SCHEMA = vol.Schema({})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up an input datetime."""
    component = EntityComponent[InputDatetime](_LOGGER, DOMAIN, hass)

    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, InputDatetime
    )

    storage_collection = DateTimeStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, InputDatetime
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

    homeassistant.helpers.service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    component.async_register_entity_service(
        "set_datetime",
        vol.All(
            cv.make_entity_service_schema(
                {
                    vol.Optional(ATTR_DATE): cv.date,
                    vol.Optional(ATTR_TIME): cv.time,
                    vol.Optional(ATTR_DATETIME): cv.datetime,
                    vol.Optional(ATTR_TIMESTAMP): vol.Coerce(float),
                },
            ),
            cv.has_at_least_one_key(
                ATTR_DATE, ATTR_TIME, ATTR_DATETIME, ATTR_TIMESTAMP
            ),
            validate_set_datetime_attrs,
        ),
        "async_set_datetime",
    )

    return True


class DateTimeStorageCollection(collection.DictStorageCollection):
    """Input storage based collection."""

    CREATE_UPDATE_SCHEMA = vol.Schema(vol.All(STORAGE_FIELDS, has_date_or_time))

    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        return self.CREATE_UPDATE_SCHEMA(data)

    @callback
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]

    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        update_data = self.CREATE_UPDATE_SCHEMA(update_data)
        return {CONF_ID: item[CONF_ID]} | update_data


class InputDatetime(collection.CollectionEntity, RestoreEntity):
    """Representation of a datetime input."""

    _unrecorded_attributes = frozenset({ATTR_EDITABLE, CONF_HAS_DATE, CONF_HAS_TIME})

    _attr_should_poll = False
    editable: bool

    def __init__(self, config: ConfigType) -> None:
        """Initialize a select input."""
        self._config = config
        self._current_datetime = None

        if not config.get(CONF_INITIAL):
            return

        current_datetime = parse_initial_datetime(config)

        # If the user passed in an initial value with a timezone, convert it to right tz
        if current_datetime.tzinfo is not None:
            self._current_datetime = current_datetime.astimezone(
                dt_util.get_default_time_zone()
            )
        else:
            self._current_datetime = current_datetime.replace(
                tzinfo=dt_util.get_default_time_zone()
            )

    @classmethod
    def from_storage(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from storage."""
        input_dt = cls(config)
        input_dt.editable = True
        return input_dt

    @classmethod
    def from_yaml(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from yaml."""
        input_dt = cls(config)
        input_dt.entity_id = f"{DOMAIN}.{config[CONF_ID]}"
        input_dt.editable = False
        return input_dt

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Priority 1: Initial value
        if self.state is not None:
            return

        default_value = py_datetime.datetime.today().strftime(f"{FMT_DATE} 00:00:00")

        # Priority 2: Old state
        if (old_state := await self.async_get_last_state()) is None:
            self._current_datetime = dt_util.parse_datetime(default_value)
            return

        if self.has_date and self.has_time:
            date_time = dt_util.parse_datetime(old_state.state)
            if date_time is None:
                current_datetime = dt_util.parse_datetime(default_value)
            else:
                current_datetime = date_time

        elif self.has_date:
            if (date := dt_util.parse_date(old_state.state)) is None:
                current_datetime = dt_util.parse_datetime(default_value)
            else:
                current_datetime = py_datetime.datetime.combine(date, DEFAULT_TIME)

        elif (time := dt_util.parse_time(old_state.state)) is None:
            current_datetime = dt_util.parse_datetime(default_value)
        else:
            current_datetime = py_datetime.datetime.combine(
                py_datetime.date.today(), time
            )

        self._current_datetime = current_datetime.replace(
            tzinfo=dt_util.get_default_time_zone()
        )

    @property
    def name(self):
        """Return the name of the select input."""
        return self._config.get(CONF_NAME)

    @property
    def has_date(self) -> bool:
        """Return True if entity has date."""
        return self._config[CONF_HAS_DATE]

    @property
    def has_time(self) -> bool:
        """Return True if entity has time."""
        return self._config[CONF_HAS_TIME]

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    def state(self):
        """Return the state of the component."""
        if self._current_datetime is None:
            return None

        if self.has_date and self.has_time:
            return self._current_datetime.strftime(FMT_DATETIME)

        if self.has_date:
            return self._current_datetime.strftime(FMT_DATE)

        return self._current_datetime.strftime(FMT_TIME)

    @property
    def capability_attributes(self) -> dict[str, Any]:
        """Return the capability attributes."""
        return {
            CONF_HAS_DATE: self.has_date,
            CONF_HAS_TIME: self.has_time,
        }

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {
            ATTR_EDITABLE: self.editable,
        }

        if self._current_datetime is None:
            return attrs

        if self.has_date and self._current_datetime is not None:
            attrs["year"] = self._current_datetime.year
            attrs["month"] = self._current_datetime.month
            attrs["day"] = self._current_datetime.day

        if self.has_time and self._current_datetime is not None:
            attrs["hour"] = self._current_datetime.hour
            attrs["minute"] = self._current_datetime.minute
            attrs["second"] = self._current_datetime.second

        if not self.has_date:
            attrs["timestamp"] = (
                self._current_datetime.hour * 3600
                + self._current_datetime.minute * 60
                + self._current_datetime.second
            )

        elif not self.has_time:
            extended = py_datetime.datetime.combine(
                self._current_datetime, py_datetime.time(0, 0)
            )
            attrs["timestamp"] = extended.timestamp()

        else:
            attrs["timestamp"] = self._current_datetime.timestamp()

        return attrs

    @property
    def unique_id(self) -> str | None:
        """Return unique id of the entity."""
        return self._config[CONF_ID]

    @callback
    def async_set_datetime(self, date=None, time=None, datetime=None, timestamp=None):
        """Set a new date / time."""
        if timestamp is not None:
            datetime = dt_util.as_local(dt_util.utc_from_timestamp(timestamp))

        if datetime:
            date = datetime.date()
            time = datetime.time()

        if not self.has_date:
            date = None

        if not self.has_time:
            time = None

        if not date and not time:
            raise vol.Invalid("Nothing to set")

        if not date:
            date = self._current_datetime.date()

        if not time:
            time = self._current_datetime.time()

        self._current_datetime = py_datetime.datetime.combine(
            date, time, dt_util.get_default_time_zone()
        )
        self.async_write_ha_state()

    async def async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        self._config = config
        self.async_write_ha_state()
