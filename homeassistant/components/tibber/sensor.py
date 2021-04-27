"""Support for Tibber sensors."""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import datetime, timedelta
import logging
from random import randrange
from typing import Any, Callable

import aiohttp
from tibber import Tibber, TibberHome

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_POWER, POWER_WATT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle, dt as dt_util

from .const import DOMAIN as TIBBER_DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:currency-usd"
SCAN_INTERVAL = timedelta(minutes=1)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[Sequence[Entity], bool], None],
) -> None:
    """Set up the Tibber sensor."""

    tibber_connection: Tibber = hass.data.get(TIBBER_DOMAIN)

    dev: list[TibberSensor] = []
    for home in tibber_connection.get_homes(only_active=False):
        try:
            await home.update_info()
        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout connecting to Tibber home: %s ", err)
            raise PlatformNotReady() from err
        except aiohttp.ClientError as err:
            _LOGGER.error("Error connecting to Tibber home: %s ", err)
            raise PlatformNotReady() from err
        if home.has_active_subscription:
            dev.append(TibberSensorElPrice(home))
        if home.has_real_time_consumption:
            dev.append(TibberSensorRT(home))

    async_add_entities(dev, True)


class TibberSensor(SensorEntity):
    """Representation of a generic Tibber sensor."""

    def __init__(self, tibber_home: TibberHome) -> None:
        """Initialize the sensor."""
        self._tibber_home = tibber_home
        self._last_updated: datetime | None = None
        self._state = None
        self._is_available = False
        self._extra_state_attributes: dict[str, str] = {}
        self._name = tibber_home.info["viewer"]["home"]["appNickname"]
        if self._name is None:
            self._name = tibber_home.info["viewer"]["home"]["address"].get(
                "address1", ""
            )
        self._spread_load_constant = randrange(3600)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        return self._extra_state_attributes

    @property
    def model(self) -> str | None:
        """Return the model of the sensor."""
        return None

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        return self._state

    @property
    def device_id(self) -> Any:
        """Return the ID of the physical device this sensor is part of."""
        home = self._tibber_home.info["viewer"]["home"]
        return home["meteringPointData"]["consumptionEan"]

    @property
    def device_info(self) -> dict[str, Any]:
        """Return the device_info of the device."""
        device_info = {
            "identifiers": {(TIBBER_DOMAIN, self.device_id)},
            "name": self.name,
            "manufacturer": MANUFACTURER,
        }
        if self.model is not None:
            device_info["model"] = self.model
        return device_info


class TibberSensorElPrice(TibberSensor):
    """Representation of a Tibber sensor for el price."""

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        now = dt_util.now()
        if (
            not self._tibber_home.last_data_timestamp
            or (self._tibber_home.last_data_timestamp - now).total_seconds()
            < 5 * 3600 + self._spread_load_constant
            or not self._is_available
        ):
            _LOGGER.debug("Asking for new data")
            await self._fetch_data()

        elif (
            self._tibber_home.current_price_total
            and self._last_updated
            and self._last_updated.hour == now.hour
            and self._tibber_home.last_data_timestamp
        ):
            return

        res = self._tibber_home.current_price_data()
        self._state, price_level, self._last_updated = res
        self._extra_state_attributes["price_level"] = price_level

        attrs = self._tibber_home.current_attributes()
        self._extra_state_attributes.update(attrs)
        self._is_available = self._state is not None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._is_available

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Electricity price {self._name}"

    @property
    def model(self) -> str:
        """Return the model of the sensor."""
        return "Price Sensor"

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return ICON

    @property
    def unit_of_measurement(self) -> Any:
        """Return the unit of measurement of this entity."""
        return self._tibber_home.price_unit

    @property
    def unique_id(self) -> Any:
        """Return a unique ID."""
        return self.device_id

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def _fetch_data(self) -> None:
        _LOGGER.debug("Fetching data")
        try:
            await self._tibber_home.update_info_and_price_info()
        except (asyncio.TimeoutError, aiohttp.ClientError):
            return
        data = self._tibber_home.info["viewer"]["home"]
        self._extra_state_attributes["app_nickname"] = data["appNickname"]
        self._extra_state_attributes["grid_company"] = data["meteringPointData"][
            "gridCompany"
        ]
        self._extra_state_attributes["estimated_annual_consumption"] = data[
            "meteringPointData"
        ]["estimatedAnnualConsumption"]


class TibberSensorRT(TibberSensor):
    """Representation of a Tibber sensor for real time consumption."""

    async def async_added_to_hass(self) -> None:
        """Start listen for real time data."""
        await self._tibber_home.rt_subscribe(self.hass.loop, self._async_callback)

    async def _async_callback(self, payload: dict[str, Any]) -> None:
        """Handle received data."""
        errors = payload.get("errors")
        if errors:
            _LOGGER.error(errors[0])
            return
        data = payload.get("data")
        if data is None:
            return
        live_measurement = data.get("liveMeasurement")
        if live_measurement is None:
            return
        self._state = live_measurement.pop("power", None)
        for key, value in live_measurement.items():
            if value is None:
                continue
            self._extra_state_attributes[key] = value

        self.async_write_ha_state()

    @property
    def available(self) -> Any:
        """Return True if entity is available."""
        return self._tibber_home.rt_subscription_running

    @property
    def model(self) -> str:
        """Return the model of the sensor."""
        return "Tibber Pulse"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Real time consumption {self._name}"

    @property
    def should_poll(self) -> bool:
        """Return the polling state."""
        return False

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return POWER_WATT

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.device_id}_rt_consumption"

    @property
    def device_class(self) -> str:
        """Return the device class of the sensor."""
        return DEVICE_CLASS_POWER
