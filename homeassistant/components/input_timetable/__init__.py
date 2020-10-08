"""Support to set a timetable (on and off times during the day)."""
import datetime
import logging
import typing

import voluptuous as vol

import homeassistant
from homeassistant.const import (
    ATTR_EDITABLE,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    SERVICE_RELOAD,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import callback
from homeassistant.helpers import collection, event
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, HomeAssistantType, ServiceCallType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "input_timetable"

ATTR_START = "start"
ATTR_END = "end"
ATTR_ON_PERIODS = "on_periods"

SERVICE_SET_ON = "set_on"
SERVICE_SET_OFF = "set_off"
SERVICE_RESET = "reset"


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: cv.schema_with_slug_keys(
            vol.Any(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_ICON): cv.icon,
                },
                None,
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_START): cv.time,
        vol.Required(ATTR_END): cv.time,
    },
    extra=vol.ALLOW_EXTRA,
)
RELOAD_SERVICE_SCHEMA = vol.Schema({})

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

CREATE_FIELDS = {
    vol.Required(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional(CONF_ICON): cv.icon,
}

UPDATE_FIELDS = {
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_ICON): cv.icon,
}


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up an input timetable."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    id_manager = collection.IDManager()

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.attach_entity_component_collection(
        component, yaml_collection, InputTimeTable.from_yaml
    )

    storage_collection = TimeTableStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        logging.getLogger(f"{__name__}.storage_collection"),
        id_manager,
    )
    collection.attach_entity_component_collection(
        component, storage_collection, InputTimeTable
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **(conf or {})} for id_, conf in config.get(DOMAIN, {}).items()]
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
            [
                {CONF_ID: id_, **(conf or {})}
                for id_, conf in conf.get(DOMAIN, {}).items()
            ]
        )

    component.async_register_entity_service(
        SERVICE_SET_ON, SERVICE_SET_SCHEMA, "async_set_on"
    )
    component.async_register_entity_service(
        SERVICE_SET_OFF, SERVICE_SET_SCHEMA, "async_set_off"
    )
    component.async_register_entity_service(SERVICE_RESET, {}, "async_reset")

    homeassistant.helpers.service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    return True


class TimeTableStorageCollection(collection.StorageCollection):
    """Input storage based collection."""

    CREATE_SCHEMA = vol.Schema(CREATE_FIELDS)
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
        self.UPDATE_SCHEMA(update_data)
        return {**data, **update_data}


class InputTimeTable(RestoreEntity):
    """Representation of a timetable."""

    def __init__(self, config: typing.Dict):
        """Initialize an input timetable."""
        self._config = config
        self._on_periods = []
        self.editable = True
        self._event_unsub = None

    @classmethod
    def from_yaml(cls, config: typing.Dict) -> "InputTimeTable":
        """Return entity instance initialized from yaml storage."""
        input_timetable = cls(config)
        input_timetable.entity_id = f"{DOMAIN}.{config[CONF_ID]}"
        input_timetable.editable = False
        return input_timetable

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the input timetable."""
        return self._config.get(CONF_NAME)

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    def state(self):
        """Return 'on' when we are in an on period."""
        now = datetime.datetime.now().time()
        for period in self._on_periods:
            if _is_in_period(now, period):
                return STATE_ON
        return STATE_OFF

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_EDITABLE: self.editable,
            ATTR_ON_PERIODS: self._on_periods_to_attribute(),
        }

    @property
    def unique_id(self) -> typing.Optional[str]:
        """Return unique id of the entity."""
        return self._config[CONF_ID]

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state and state.attributes.get(ATTR_ON_PERIODS):
            self._on_periods_from_attribute(state.attributes[ATTR_ON_PERIODS])
        self._update_state()

    def _on_periods_to_attribute(self):
        return [
            {ATTR_START: period.start.isoformat(), ATTR_END: period.end.isoformat()}
            for period in self._on_periods
        ]

    def _on_periods_from_attribute(self, periods):
        self._on_periods = [
            Period(_read_time(period[ATTR_START]), _read_time(period[ATTR_END]))
            for period in periods
        ]

    async def async_set_on(self, start, end):
        """Add on period."""
        start = start.replace(microsecond=0, tzinfo=None)
        end = end.replace(microsecond=0, tzinfo=None)
        if end <= start:
            raise vol.Invalid("Start time must be earlier than end time")

        # Merge overlapping and adjusting periods.
        for period in self._on_periods:
            if _is_in_period(start, period) or start == period.end:
                start = period.start
            if _is_in_period(end, period) or end == period.start:
                end = period.end

        on_periods = [Period(start, end)]

        # Copy non overlapping periods.
        for period in self._on_periods:
            if period.end <= start or period.start >= end:
                on_periods.append(period)

        on_periods.sort(key=lambda period: period.start)

        self._on_periods = on_periods
        self._update_state()

    async def async_set_off(self, start, end):
        """Add off period (subtracting the on periods)."""
        start = start.replace(microsecond=0, tzinfo=None)
        end = end.replace(microsecond=0, tzinfo=None)
        if end <= start:
            raise vol.Invalid("Start time must be earlier than end time")

        on_periods = []

        # Trim and split periods.
        for period in self._on_periods:
            if _is_in_period(start, period):
                self._on_periods.remove(period)
                if start > period.start:
                    on_periods.append(Period(period.start, start))
                if _is_in_period(end, period):
                    on_periods.append(Period(end, period.end))
                break
        for period in self._on_periods:
            if _is_in_period(end, period):
                self._on_periods.remove(period)
                on_periods.append(Period(period.start, end))
                break

        # Copy non overlapping periods.
        for period in self._on_periods:
            if period.end <= start or period.start >= end:
                on_periods.append(period)

        on_periods.sort(key=lambda period: period.start)

        self._on_periods = on_periods
        self._update_state()

    async def async_reset(self):
        """Delete all on periods."""
        self._on_periods = []
        self._update_state()

    async def async_update_config(self, config: typing.Dict) -> None:
        """Handle when the config is updated."""
        self._config = config
        self._update_state()

    def _schedule_update(self):
        if self._event_unsub:
            self._event_unsub()
            self._event_unsub = None

        if not self._on_periods:
            return

        now = datetime.datetime.now()
        time = now.time()
        midnight = datetime.time.fromisoformat("00:00:00")
        prev_end = midnight
        for period in self._on_periods:
            if _is_in_period(time, period):
                next_change = datetime.datetime.combine(now.date(), period.end)
                break
            if prev_end <= time < period.start:
                next_change = datetime.datetime.combine(now.date(), period.start)
                break
            prev_end = period.end
        else:
            next_change = datetime.datetime.combine(
                datetime.date.today() + datetime.timedelta(days=1), midnight
            )

        self._event_unsub = event.async_track_point_in_time(
            self.hass, self._update_state, next_change
        )

    @callback
    def _update_state(self, now=None):
        """Update the state to reflect the current time."""
        self._schedule_update()
        self.async_write_ha_state()


class Period:
    """Simple time range."""

    def __init__(self, start, end):
        """Initialize the range."""
        self.start = start
        self.end = end


def _read_time(value):
    return datetime.time.fromisoformat(value).replace(microsecond=0, tzinfo=None)


def _is_in_period(value, period):
    return period.start <= value < period.end
