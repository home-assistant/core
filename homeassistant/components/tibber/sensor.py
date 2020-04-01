"""Support for Tibber sensors."""
import asyncio
from datetime import timedelta
import logging

import aiohttp

from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle, dt as dt_util

from . import DOMAIN as TIBBER_DOMAIN

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:currency-usd"
ICON_RT = "mdi:power-plug"
SCAN_INTERVAL = timedelta(minutes=1)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Tibber sensor."""
    if discovery_info is None:
        return

    tibber_connection = hass.data.get(TIBBER_DOMAIN)

    dev = []
    for home in tibber_connection.get_homes(only_active=False):
        try:
            await home.update_info()
        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout connecting to Tibber home: %s ", err)
            raise PlatformNotReady()
        except aiohttp.ClientError as err:
            _LOGGER.error("Error connecting to Tibber home: %s ", err)
            raise PlatformNotReady()
        if home.has_active_subscription:
            dev.append(TibberSensorElPrice(home))
        if home.has_real_time_consumption:
            dev.append(TibberSensorRT(home))

    async_add_entities(dev, True)


class TibberSensor(Entity):
    """Representation of a generic Tibber sensor."""

    def __init__(self, tibber_home):
        """Initialize the sensor."""
        self._tibber_home = tibber_home
        self._last_updated = None
        self._state = None
        self._is_available = False
        self._device_state_attributes = {}
        self._name = tibber_home.info["viewer"]["home"]["appNickname"]
        if self._name is None:
            self._name = tibber_home.info["viewer"]["home"]["address"].get(
                "address1", ""
            )

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._device_state_attributes

    @property
    def state(self):
        """Return the state of the device."""
        return self._state


class TibberSensorElPrice(TibberSensor):
    """Representation of a Tibber sensor for el price."""

    async def async_update(self):
        """Get the latest data and updates the states."""
        now = dt_util.now()
        if (
            self._tibber_home.current_price_total
            and self._last_updated
            and self._last_updated.hour == now.hour
            and self._tibber_home.last_data_timestamp
        ):
            return

        if (
            not self._tibber_home.last_data_timestamp
            or (self._tibber_home.last_data_timestamp - now).total_seconds() / 3600 < 12
            or not self._is_available
        ):
            _LOGGER.debug("Asking for new data.")
            await self._fetch_data()

        res = self._tibber_home.current_price_data()
        self._state, price_level, self._last_updated = res
        self._device_state_attributes["price_level"] = price_level

        attrs = self._tibber_home.current_attributes()
        self._device_state_attributes.update(attrs)
        self._is_available = self._state is not None

    @property
    def available(self):
        """Return True if entity is available."""
        return self._is_available

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Electricity price {}".format(self._name)

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._tibber_home.price_unit

    @property
    def unique_id(self):
        """Return a unique ID."""
        home = self._tibber_home.info["viewer"]["home"]
        return home["meteringPointData"]["consumptionEan"]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def _fetch_data(self):
        try:
            await self._tibber_home.update_info()
            await self._tibber_home.update_price_info()
        except (asyncio.TimeoutError, aiohttp.ClientError):
            return
        data = self._tibber_home.info["viewer"]["home"]
        self._device_state_attributes["app_nickname"] = data["appNickname"]
        self._device_state_attributes["grid_company"] = data["meteringPointData"][
            "gridCompany"
        ]
        self._device_state_attributes["estimated_annual_consumption"] = data[
            "meteringPointData"
        ]["estimatedAnnualConsumption"]


class TibberSensorRT(TibberSensor):
    """Representation of a Tibber sensor for real time consumption."""

    async def async_added_to_hass(self):
        """Start unavailability tracking."""
        await self._tibber_home.rt_subscribe(self.hass.loop, self._async_callback)

    async def _async_callback(self, payload):
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
            self._device_state_attributes[key] = value

        self.async_write_ha_state()

    @property
    def available(self):
        """Return True if entity is available."""
        return self._tibber_home.rt_subscription_running

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Real time consumption {}".format(self._name)

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON_RT

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return "W"

    @property
    def unique_id(self):
        """Return a unique ID."""
        home = self._tibber_home.info["viewer"]["home"]
        _id = home["meteringPointData"]["consumptionEan"]
        return f"{_id}_rt_consumption"
