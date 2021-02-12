"""Support to select a date and/or a time."""
from __future__ import annotations

import datetime as py_datetime
import logging
import typing

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
from homeassistant.core import callback
from homeassistant.helpers import collection
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.helpers.service
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, HomeAssistantType, ServiceCallType
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

CREATE_FIELDS = {
    vol.Required(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional(CONF_HAS_DATE, default=False): cv.boolean,
    vol.Optional(CONF_HAS_TIME, default=False): cv.boolean,
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_INITIAL): cv.string,
}
UPDATE_FIELDS = {
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_HAS_DATE): cv.boolean,
    vol.Optional(CONF_HAS_TIME): cv.boolean,
    vol.Optional(CONF_ICON): cv.icon,
    vol.Optional(CONF_INITIAL): cv.string,
}


def has_date_or_time(conf):
    """Check at least date or time is true."""
    if conf[CONF_HAS_DATE] or conf[CONF_HAS_TIME]:
        return conf

    raise vol.Invalid("Entity needs at least a date or a time")


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
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)
RELOAD_SERVICE_SCHEMA = vol.Schema({})


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up an input datetime."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, InputDatetime.from_yaml
    )

    storage_collection = DateTimeStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        logging.getLogger(f"{__name__}.storage_collection"),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, InputDatetime
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **cfg} for id_, cfg in config.get(DOMAIN, {}).items()]
    )
    await storage_collection.async_load()

    collection.StorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

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
        "set_datetime",
        vol.All(
            vol.Schema(
                {
                    vol.Optional(ATTR_DATE): cv.date,
                    vol.Optional(ATTR_TIME): cv.time,
                    vol.Optional(ATTR_DATETIME): cv.datetime,
                    vol.Optional(ATTR_TIMESTAMP): vol.Coerce(float),
                },
                extra=vol.ALLOW_EXTRA,
            ),
            cv.has_at_least_one_key(
                ATTR_DATE, ATTR_TIME, ATTR_DATETIME, ATTR_TIMESTAMP
            ),
            validate_set_datetime_attrs,
        ),
        "async_set_datetime",
    )

    return True


class DateTimeStorageCollection(collection.StorageCollection):
    """Input storage based collection."""

    CREATE_SCHEMA = vol.Schema(vol.All(CREATE_FIELDS, has_date_or_time))
    UPDATE_SCHEMA = vol.Schema(UPDATE_FIELDS)

    async def _process_create_data(self, data: typing.Dict) -> typing.Dict:
        """Validate the config is valid."""
        return self.CREATE_SCHEMA(data)

    @callback
    def _get_suggested_id(self, info: typing.Dict) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]

    async def _update_data(self, data: dict, update_data: typing.Dict) -> typing.Dict:
        """Return a new updated data object."""
        update_data = self.UPDATE_SCHEMA(update_data)
        return has_date_or_time({**data, **update_data})


class InputDatetime(RestoreEntity):
    """Representation of a datetime input."""

    def __init__(self, config: typing.Dict) -> None:
        """Initialize a select input."""
        self._config = config
        self.editable = True
        self._current_datetime = None

        initial = config.get(CONF_INITIAL)
        if not initial:
            return

        if self.has_date and self.has_time:
            current_datetime = dt_util.parse_datetime(initial)

        elif self.has_date:
            date = dt_util.parse_date(initial)
            current_datetime = py_datetime.datetime.combine(date, DEFAULT_TIME)

        else:
            time = dt_util.parse_time(initial)
            current_datetime = py_datetime.datetime.combine(
                py_datetime.date.today(), time
            )

        # If the user passed in an initial value with a timezone, convert it to right tz
        if current_datetime.tzinfo is not None:
            self._current_datetime = current_datetime.astimezone(
                dt_util.DEFAULT_TIME_ZONE
            )
        else:
            self._current_datetime = dt_util.DEFAULT_TIME_ZONE.localize(
                current_datetime
            )

    @classmethod
    def from_yaml(cls, config: typing.Dict) -> InputDatetime:
        """Return entity instance initialized from yaml storage."""
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

        default_value = py_datetime.datetime.today().strftime("%Y-%m-%d 00:00:00")

        # Priority 2: Old state
        old_state = await self.async_get_last_state()
        if old_state is None:
            self._current_datetime = dt_util.parse_datetime(default_value)
            return

        if self.has_date and self.has_time:
            date_time = dt_util.parse_datetime(old_state.state)
            if date_time is None:
                current_datetime = dt_util.parse_datetime(default_value)
            else:
                current_datetime = date_time

        elif self.has_date:
            date = dt_util.parse_date(old_state.state)
            if date is None:
                current_datetime = dt_util.parse_datetime(default_value)
            else:
                current_datetime = py_datetime.datetime.combine(date, DEFAULT_TIME)

        else:
            time = dt_util.parse_time(old_state.state)
            if time is None:
                current_datetime = dt_util.parse_datetime(default_value)
            else:
                current_datetime = py_datetime.datetime.combine(
                    py_datetime.date.today(), time
                )

        self._current_datetime = current_datetime.replace(
            tzinfo=dt_util.DEFAULT_TIME_ZONE
        )

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

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
    def state_attributes(self):
        """Return the state attributes."""
        attrs = {
            ATTR_EDITABLE: self.editable,
            CONF_HAS_DATE: self.has_date,
            CONF_HAS_TIME: self.has_time,
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
    def unique_id(self) -> typing.Optional[str]:
        """Return unique id of the entity."""
        return self._config[CONF_ID]

    @callback
    def async_set_datetime(self, date=None, time=None, datetime=None, timestamp=None):
        """Set a new date / time."""
        if timestamp:
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

        self._current_datetime = dt_util.DEFAULT_TIME_ZONE.localize(
            py_datetime.datetime.combine(date, time)
        )
        self.async_write_ha_state()

    async def async_update_config(self, config: typing.Dict) -> None:
        """Handle when the config is updated."""
        self._config = config
        self.async_write_ha_state()
