"""Easee Charger base entity class."""
import asyncio
from datetime import datetime
import logging
from typing import Any, Callable, Dict, List

from easee import Charger, ChargerConfig, ChargerState, Circuit, Site
from easee.charger import ChargerSchedule

from homeassistant.helpers.entity import Entity
from homeassistant.util import dt

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def round_2_dec(value, unit=None):
    """Round to two decimals."""
    if unit in ("W", "Wh"):
        value = value * 1000
    return round(value, 2)


convert_units_funcs = {
    "round_2_dec": round_2_dec,
}


class ChargerData:
    """Representation charger data."""

    def __init__(self, charger: Charger, circuit: Circuit, site: Site):
        """Initialize the charger data."""
        self.charger: Charger = charger
        self.circuit: Circuit = circuit
        self.site: Site = site
        self.state: List[ChargerState] = {}
        self.config: List[ChargerConfig] = {}
        self.schedule: List[ChargerSchedule] = {}

    async def async_refresh(self, now=None):
        """Refresh data for charger."""
        self.state = await self.charger.get_state()
        self.config = await self.charger.get_config()
        self.schedule = await self.charger.get_basic_charge_plan()
        _LOGGER.debug("Schedule: %s", self.schedule)


class ChargersData:
    """Representation chargers data."""

    def __init__(self, chargers: List[ChargerData], entities: List[Any]):
        """Initialize the chargers data."""
        self.chargers = chargers
        self.entities = entities

    async def async_refresh(self, now=None):
        """Fetch new state data for the entities."""
        tasks = [charger.async_refresh() for charger in self.chargers]
        if tasks:
            await asyncio.wait(tasks)

        # Schedule an update for all included entities
        for entity in self.entities:
            entity.async_schedule_update_ha_state(True)


class ChargerEntity(Entity):
    """Implementation of Easee charger entity."""

    def __init__(
        self,
        charger_data: ChargerData,
        name: str,
        state_key: str,
        units: str,
        convert_units_func: Callable,
        attrs_keys: List[str],
        icon: str,
        state_func=None,
    ):
        """Initialize the entity."""
        self.charger_data = charger_data
        self._entity_name = name
        self._state_key = state_key
        self._units = units
        self._convert_units_func = convert_units_func
        self._attrs_keys = attrs_keys
        self._icon = icon
        self._state_func = state_func
        self._state = None

    @property
    def name(self):
        """Return the name of the entity."""
        return f"{DOMAIN}_charger_{self.charger_data.charger.id}_{self._entity_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.charger_data.charger.id}_{self._entity_name}"

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self.charger_data.charger.id)},
            "name": self.charger_data.charger.name,
            "manufacturer": "Easee",
            "model": "Charging Robot",
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._units

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state is not None

    @property
    def state_attributes(self):
        """Return the state attributes."""
        try:
            attrs = {
                "name": self.charger_data.charger.name,
                "id": self.charger_data.charger.id,
            }
            for attr_key in self._attrs_keys:
                key = attr_key
                if "site" in attr_key or "circuit" in attr_key:
                    # maybe for everything?
                    key = attr_key.replace(".", "_")
                attrs[key] = self.get_value_from_key(attr_key)

            return attrs
        except IndexError:
            return {}

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    def get_value_from_key(self, key):
        """Get the value for the sensor key."""
        first, second = key.split(".")
        value = None
        if first == "config":
            value = self.charger_data.config[second]
        elif first == "state":
            value = self.charger_data.state[second]
        elif first == "circuit":
            value = self.charger_data.circuit[second]
        elif first == "site":
            value = self.charger_data.site[second]
        elif first == "schedule":
            if self.charger_data.schedule is not None:
                value = self.charger_data.schedule[second]
        else:
            _LOGGER.error("Unknown first part of key: %s", key)
            raise IndexError("Unknown first part of key")

        if isinstance(value, datetime):
            value = dt.as_local(value)
        return value

    async def async_update(self):
        """Get the latest data and update the state."""
        _LOGGER.debug(
            "ChargerEntity async_update : %s %s",
            self.charger_data.charger.id,
            self._entity_name,
        )
        try:
            self._state = self.get_value_from_key(self._state_key)
            if self._state_func is not None:
                if self._state_key.startswith("state"):
                    self._state = self._state_func(self.charger_data.state)
                if self._state_key.startswith("config"):
                    self._state = self._state_func(self.charger_data.config)
                if self._state_key.startswith("schedule"):
                    self._state = self._state_func(self.charger_data.schedule)
            if self._convert_units_func is not None:
                self._state = self._convert_units_func(self._state, self._units)

        except IndexError as ex:
            raise IndexError("Wrong key for entity: %s" % self._state_key) from ex
