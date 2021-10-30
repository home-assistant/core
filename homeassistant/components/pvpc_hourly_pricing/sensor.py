"""Sensor to collect the reference daily prices of electricity ('PVPC') in Spain."""
from __future__ import annotations

import logging
from random import randint
from typing import Any

from aiopvpc import PVPCData

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CURRENCY_EURO, ENERGY_KILO_WATT_HOUR
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_time_change
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.dt as dt_util

from .const import ATTR_POWER, ATTR_POWER_P3, ATTR_TARIFF

_LOGGER = logging.getLogger(__name__)

ATTR_PRICE = "price"
ICON = "mdi:currency-eur"
UNIT = f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}"

_DEFAULT_TIMEOUT = 10


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the electricity price sensor from config_entry."""
    name = config_entry.data[CONF_NAME]
    pvpc_data_handler = PVPCData(
        tariff=config_entry.data[ATTR_TARIFF],
        power=config_entry.data[ATTR_POWER],
        power_valley=config_entry.data[ATTR_POWER_P3],
        local_timezone=hass.config.time_zone,
        websession=async_get_clientsession(hass),
        timeout=_DEFAULT_TIMEOUT,
    )
    async_add_entities(
        [ElecPriceSensor(name, config_entry.unique_id, pvpc_data_handler)], False
    )


class ElecPriceSensor(RestoreEntity, SensorEntity):
    """Class to hold the prices of electricity as a sensor."""

    _attr_icon = ICON
    _attr_native_unit_of_measurement = UNIT
    _attr_should_poll = False
    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, name, unique_id, pvpc_data_handler):
        """Initialize the sensor object."""
        self._name = name
        self._unique_id = unique_id
        self._pvpc_data = pvpc_data_handler
        self._num_retries = 0

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._pvpc_data.state = state.state

        # Update 'state' value in hour changes
        self.async_on_remove(
            async_track_time_change(
                self.hass, self.update_current_price, second=[0], minute=[0]
            )
        )
        # Update prices at random time, 2 times/hour (don't want to upset API)
        random_minute = randint(1, 29)
        mins_update = [random_minute, random_minute + 30]
        self.async_on_remove(
            async_track_time_change(
                self.hass, self.async_update_prices, second=[0], minute=mins_update
            )
        )
        _LOGGER.debug(
            "Setup of price sensor %s (%s) with tariff '%s', "
            "updating prices each hour at %s min",
            self.name,
            self.entity_id,
            self._pvpc_data.tariff,
            mins_update,
        )
        now = dt_util.utcnow()
        await self.async_update_prices(now)
        self.update_current_price(now)

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self._pvpc_data.state

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._pvpc_data.state_available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self._pvpc_data.attributes

    @callback
    def update_current_price(self, now):
        """Update the sensor state, by selecting the current price for this hour."""
        self._pvpc_data.process_state_and_attributes(now)
        self.async_write_ha_state()

    async def async_update_prices(self, now):
        """Update electricity prices from the ESIOS API."""
        prices = await self._pvpc_data.async_update_prices(now)
        if not prices and self._pvpc_data.source_available:
            self._num_retries += 1
            if self._num_retries > 2:
                _LOGGER.warning(
                    "%s: repeated bad data update, mark component as unavailable source",
                    self.entity_id,
                )
                self._pvpc_data.source_available = False
                return

            retry_delay = 2 * self._num_retries * self._pvpc_data.timeout
            _LOGGER.debug(
                "%s: Bad update[retry:%d], will try again in %d s",
                self.entity_id,
                self._num_retries,
                retry_delay,
            )
            async_call_later(self.hass, retry_delay, self.async_update_prices)
            return

        if not prices:
            _LOGGER.debug("%s: data source is not yet available", self.entity_id)
            return

        self._num_retries = 0
        if not self._pvpc_data.source_available:
            self._pvpc_data.source_available = True
            _LOGGER.warning("%s: component has recovered data access", self.entity_id)
            self.update_current_price(now)
