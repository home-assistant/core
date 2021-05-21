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
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_VOLTAGE,
    SensorEntity,
)
from homeassistant.const import (
    ELECTRICAL_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    SIGNAL_STRENGTH_DECIBELS,
    VOLT,
)
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.device_registry import async_get as async_get_dev_reg
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_registry import async_get as async_get_entity_reg
from homeassistant.util import Throttle, dt as dt_util

from .const import DOMAIN as TIBBER_DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:currency-usd"
SCAN_INTERVAL = timedelta(minutes=1)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)
PARALLEL_UPDATES = 0
SIGNAL_UPDATE_ENTITY = "tibber_rt_update_{}"

RT_SENSOR_MAP = {
    "averagePower": ["average power", DEVICE_CLASS_POWER, POWER_WATT],
    "power": ["power", DEVICE_CLASS_POWER, POWER_WATT],
    "minPower": ["min power", DEVICE_CLASS_POWER, POWER_WATT],
    "maxPower": ["max power", DEVICE_CLASS_POWER, POWER_WATT],
    "accumulatedConsumption": [
        "accumulated consumption",
        DEVICE_CLASS_ENERGY,
        ENERGY_KILO_WATT_HOUR,
    ],
    "accumulatedConsumptionLastHour": [
        "accumulated consumption last hour",
        DEVICE_CLASS_ENERGY,
        ENERGY_KILO_WATT_HOUR,
    ],
    "accumulatedProduction": [
        "accumulated production",
        DEVICE_CLASS_ENERGY,
        ENERGY_KILO_WATT_HOUR,
    ],
    "accumulatedProductionLastHour": [
        "accumulated production last hour",
        DEVICE_CLASS_ENERGY,
        ENERGY_KILO_WATT_HOUR,
    ],
    "lastMeterConsumption": [
        "last meter consumption",
        DEVICE_CLASS_ENERGY,
        ENERGY_KILO_WATT_HOUR,
    ],
    "lastMeterProduction": [
        "last meter production",
        DEVICE_CLASS_ENERGY,
        ENERGY_KILO_WATT_HOUR,
    ],
    "voltagePhase1": ["voltage phase1", DEVICE_CLASS_VOLTAGE, VOLT],
    "voltagePhase2": ["voltage phase2", DEVICE_CLASS_VOLTAGE, VOLT],
    "voltagePhase3": ["voltage phase3", DEVICE_CLASS_VOLTAGE, VOLT],
    "currentL1": ["current L1", DEVICE_CLASS_CURRENT, ELECTRICAL_CURRENT_AMPERE],
    "currentL2": ["current L2", DEVICE_CLASS_CURRENT, ELECTRICAL_CURRENT_AMPERE],
    "currentL3": ["current L3", DEVICE_CLASS_CURRENT, ELECTRICAL_CURRENT_AMPERE],
    "signalStrength": [
        "signal strength",
        DEVICE_CLASS_SIGNAL_STRENGTH,
        SIGNAL_STRENGTH_DECIBELS,
    ],
    "accumulatedCost": ["accumulated cost", None, None],
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Tibber sensor."""

    tibber_connection = hass.data.get(TIBBER_DOMAIN)

    entity_registry = async_get_entity_reg(hass)
    device_registry = async_get_dev_reg(hass)

    entities = []
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
            entities.append(TibberSensorElPrice(home))
        if home.has_real_time_consumption:
            await home.rt_subscribe(
                TibberRtDataHandler(async_add_entities, home, hass).async_callback
            )

        # migrate
        old_id = home.info["viewer"]["home"]["meteringPointData"]["consumptionEan"]
        if old_id is None:
            continue

        # migrate to new device ids
        old_entity_id = entity_registry.async_get_entity_id(
            "sensor", TIBBER_DOMAIN, old_id
        )
        if old_entity_id is not None:
            entity_registry.async_update_entity(
                old_entity_id, new_unique_id=home.home_id
            )

        # migrate to new device ids
        device_entry = device_registry.async_get_device({(TIBBER_DOMAIN, old_id)})
        if device_entry and entry.entry_id in device_entry.config_entries:
            device_registry.async_update_device(
                device_entry.id, new_identifiers={(TIBBER_DOMAIN, home.home_id)}
            )

    async_add_entities(entities, True)


class TibberSensor(SensorEntity):
    """Representation of a generic Tibber sensor."""

    def __init__(self, tibber_home):
        """Initialize the sensor."""
        self._tibber_home = tibber_home
        self._state = None

        self._name = tibber_home.info["viewer"]["home"]["appNickname"]
        if self._name is None:
            self._name = tibber_home.info["viewer"]["home"]["address"].get(
                "address1", ""
            )

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

    def __init__(self, tibber_home):
        """Initialize the sensor."""
        super().__init__(tibber_home)
        self._last_updated = None
        self._is_available = False
        self._extra_state_attributes = {}
        self._spread_load_constant = randrange(5000)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._extra_state_attributes

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

    def __init__(self, tibber_home, sensor_name, device_class, unit, initial_state):
        """Initialize the sensor."""
        super().__init__(tibber_home)
        self._sensor_name = sensor_name
        self._device_class = device_class
        self._unit = unit
        self._state = initial_state

    async def async_added_to_hass(self):
        """Start listen for real time data."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE_ENTITY.format(self._sensor_name),
                self._set_state,
            )
        )

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
        return f"{self._sensor_name} {self._name}"

    @callback
    def _set_state(self, state):
        """Set sensor state."""
        self._state = state
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
        return f"{self.device_id}_rt_{self._sensor_name}"

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
        self._entities = set()

    async def async_callback(self, payload):
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

        new_entities = []
        for sensor_type, state in live_measurement.items():
            if state is None or sensor_type not in RT_SENSOR_MAP:
                continue
            if sensor_type in self._entities:
                async_dispatcher_send(
                    self.hass,
                    SIGNAL_UPDATE_ENTITY.format(RT_SENSOR_MAP[sensor_type][0]),
                    state,
                )
            else:
                sensor_name, device_class, unit = RT_SENSOR_MAP[sensor_type]
                if sensor_type == "accumulatedCost":
                    unit = self._tibber_home.currency
                entity = TibberSensorRT(
                    self._tibber_home, sensor_name, device_class, unit, state
                )
                new_entities.append(entity)
                self._entities.add(sensor_type)
        if new_entities:
            self._async_add_entities(new_entities)
