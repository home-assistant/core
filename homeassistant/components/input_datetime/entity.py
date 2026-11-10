"""Entities for the Input datetime integration."""

import datetime as dt
from typing import Any, Self, override

import probatio

from homeassistant.const import CONF_ICON, CONF_ID, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import collection
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HAS_DATE,
    CONF_HAS_TIME,
    CONF_INITIAL,
    DEFAULT_TIME,
    DOMAIN,
    FMT_DATE,
    FMT_DATETIME,
    FMT_TIME,
    InputDatetimeEntityCapabilityAttribute,
    InputDatetimeEntityStateAttribute,
)


def parse_initial_datetime(conf: dict[str, Any]) -> dt.datetime:
    """Check the initial value is valid."""
    initial: str = conf[CONF_INITIAL]

    if conf[CONF_HAS_DATE] and conf[CONF_HAS_TIME]:
        if (datetime := dt_util.parse_datetime(initial)) is not None:
            return datetime
        raise probatio.Invalid(
            f"Initial value '{initial}' can't be parsed as a datetime"
        )

    if conf[CONF_HAS_DATE]:
        if (date := dt_util.parse_date(initial)) is not None:
            return dt.datetime.combine(date, DEFAULT_TIME)
        raise probatio.Invalid(f"Initial value '{initial}' can't be parsed as a date")

    if (time := dt_util.parse_time(initial)) is not None:
        return dt.datetime.combine(dt_util.now().date(), time)
    raise probatio.Invalid(f"Initial value '{initial}' can't be parsed as a time")


class InputDatetime(collection.CollectionEntity, RestoreEntity):
    """Representation of a datetime input."""

    _unrecorded_attributes = frozenset(
        {
            InputDatetimeEntityStateAttribute.EDITABLE,
            InputDatetimeEntityCapabilityAttribute.HAS_DATE,
            InputDatetimeEntityCapabilityAttribute.HAS_TIME,
        }
    )

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
    @override
    def from_storage(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from storage."""
        input_dt = cls(config)
        input_dt.editable = True
        return input_dt

    @classmethod
    @override
    def from_yaml(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from yaml."""
        input_dt = cls(config)
        input_dt.entity_id = f"{DOMAIN}.{config[CONF_ID]}"
        input_dt.editable = False
        return input_dt

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Priority 1: Initial value
        if self.state is not None:
            return

        default_value = dt_util.now().strftime(f"{FMT_DATE} 00:00:00")

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
                current_datetime = dt.datetime.combine(date, DEFAULT_TIME)

        elif (time := dt_util.parse_time(old_state.state)) is None:
            current_datetime = dt_util.parse_datetime(default_value)
        else:
            current_datetime = dt.datetime.combine(dt_util.now().date(), time)

        self._current_datetime = current_datetime.replace(  # type: ignore[union-attr]
            tzinfo=dt_util.get_default_time_zone()
        )

    @property
    @override
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
    @override
    def icon(self) -> str | None:
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    @override
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
    @override
    def capability_attributes(self) -> dict[str, Any]:
        """Return the capability attributes."""
        return {
            InputDatetimeEntityCapabilityAttribute.HAS_DATE: self.has_date,
            InputDatetimeEntityCapabilityAttribute.HAS_TIME: self.has_time,
        }

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs: dict[str, Any] = {
            InputDatetimeEntityStateAttribute.EDITABLE: self.editable,
        }

        if self._current_datetime is None:
            return attrs

        if self.has_date and self._current_datetime is not None:
            attrs[InputDatetimeEntityStateAttribute.YEAR] = self._current_datetime.year
            attrs[InputDatetimeEntityStateAttribute.MONTH] = (
                self._current_datetime.month
            )
            attrs[InputDatetimeEntityStateAttribute.DAY] = self._current_datetime.day

        if self.has_time and self._current_datetime is not None:
            attrs[InputDatetimeEntityStateAttribute.HOUR] = self._current_datetime.hour
            attrs[InputDatetimeEntityStateAttribute.MINUTE] = (
                self._current_datetime.minute
            )
            attrs[InputDatetimeEntityStateAttribute.SECOND] = (
                self._current_datetime.second
            )

        if not self.has_date:
            attrs[InputDatetimeEntityStateAttribute.TIMESTAMP] = (
                self._current_datetime.hour * 3600
                + self._current_datetime.minute * 60
                + self._current_datetime.second
            )

        elif not self.has_time:
            extended = dt.datetime.combine(
                self._current_datetime,
                dt.time(0, 0),
                dt_util.get_default_time_zone(),
            )
            attrs[InputDatetimeEntityStateAttribute.TIMESTAMP] = extended.timestamp()

        else:
            attrs[InputDatetimeEntityStateAttribute.TIMESTAMP] = (
                self._current_datetime.timestamp()
            )

        return attrs

    @property
    @override
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
            raise probatio.Invalid("Nothing to set")

        if not date:
            date = self._current_datetime.date()

        if not time:
            time = self._current_datetime.time()

        self._current_datetime = dt.datetime.combine(
            date, time, dt_util.get_default_time_zone()
        )
        self.async_write_ha_state()

    @override
    async def async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        self._config = config
        self.async_write_ha_state()
