"""Support for Tibber sensors."""
import asyncio
from datetime import timedelta
import logging
from random import randrange

import aiohttp

from homeassistant.components.sensor import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_VOLTAGE,
    SensorEntity,
)
from homeassistant.const import (
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    EVENT_HOMEASSISTANT_START,
    POWER_WATT,
    SIGNAL_STRENGTH_DECIBELS,
    VOLT,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import Throttle, dt as dt_util

from .const import DOMAIN as TIBBER_DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:currency-usd"
SCAN_INTERVAL = timedelta(minutes=1)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)
PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Tibber sensor."""

    tibber_connection = hass.data.get(TIBBER_DOMAIN)

    dev = []
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
            TibberRtDataHandler(async_add_entities, home, hass)
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START,
                TibberRtDataHandler(async_add_entities, home, hass).hass_started,
            )

    async_add_entities(dev, True)


class TibberSensor(SensorEntity):
    """Representation of a generic Tibber sensor."""

    def __init__(self, tibber_home):
        """Initialize the sensor."""
        self._tibber_home = tibber_home
        self._last_updated = None
        self._state = None
        self._is_available = False
        self._extra_state_attributes = {}
        self._name = tibber_home.info["viewer"]["home"]["appNickname"]
        if self._name is None:
            self._name = tibber_home.info["viewer"]["home"]["address"].get(
                "address1", ""
            )
        self._spread_load_constant = randrange(3600)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._extra_state_attributes

    @property
    def model(self):
        """Return the model of the sensor."""
        return None

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def device_id(self):
        """Return the ID of the physical device this sensor is part of."""
        return self._tibber_home.home_id

    @property
    def device_info(self):
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

    async def async_update(self):
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
    def available(self):
        """Return True if entity is available."""
        return self._is_available

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Electricity price {self._name}"

    @property
    def model(self):
        """Return the model of the sensor."""
        return "Price Sensor"

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
        return self.device_id

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def _fetch_data(self):
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

    def __init__(self, tibber_home, sensor, unit, device_class=None):
        """Initialize the sensor."""
        super().__init__(tibber_home)
        self._sensor = sensor
        self._unit = unit
        self._device_class = device_class

    @property
    def available(self):
        """Return True if entity is available."""
        return self._tibber_home.rt_subscription_running

    @property
    def model(self):
        """Return the model of the sensor."""
        return "Tibber Pulse"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Real time {self._sensor} {self._name}"

    def set_state(self, state):
        """Set sensor state."""
        self._state = state
        if self.hass is None:
            return
        self.async_write_ha_state()

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self.device_id}_rt_{self._sensor}"

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class


class TibberRtDataHandler:
    """Handle Tibber realtime data."""

    def __init__(self, async_add_entities, tibber_home, hass):
        """Initialize the data handler."""
        self._async_add_entities = async_add_entities
        self._tibber_home = tibber_home
        self.hass = hass
        self._sensors = {}

    async def hass_started(self, _):
        """Start listen for real time data."""
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

        for sensor, value in live_measurement.items():
            if value is None:
                continue
            if sensor not in self._sensors:
                if sensor in [
                    "power",
                    "powerProduction",
                    "minPower",
                    "averagePower",
                    "maxPower",
                ]:
                    dev = TibberSensorRT(
                        self._tibber_home, sensor, POWER_WATT, DEVICE_CLASS_POWER
                    )
                elif sensor in [
                    "accumulatedProduction",
                    "accumulatedConsumption",
                    "lastMeterConsumption",
                    "lastMeterProduction",
                    "accumulatedConsumptionLastHour",
                    "accumulatedProductionLastHour",
                ]:
                    dev = TibberSensorRT(
                        self._tibber_home,
                        sensor,
                        ENERGY_KILO_WATT_HOUR,
                        DEVICE_CLASS_ENERGY,
                    )
                elif sensor in ["voltagePhase1", "voltagePhase2", "voltagePhase3"]:
                    dev = TibberSensorRT(
                        self._tibber_home, sensor, VOLT, DEVICE_CLASS_VOLTAGE
                    )
                elif sensor in ["currentL1", "currentL2", "currentL3"]:
                    dev = TibberSensorRT(
                        self._tibber_home,
                        sensor,
                        ELECTRICAL_CURRENT_AMPERE,
                        DEVICE_CLASS_CURRENT,
                    )
                elif sensor in ["signalStrength"]:
                    dev = TibberSensorRT(
                        self._tibber_home, sensor, SIGNAL_STRENGTH_DECIBELS
                    )
                elif sensor in ["accumulatedCost"]:
                    dev = TibberSensorRT(
                        self._tibber_home, sensor, live_measurement.get("currency")
                    )
                else:
                    continue
                self._async_add_entities([dev])
                self._sensors[sensor] = dev
            self._sensors[sensor].set_state(value)
