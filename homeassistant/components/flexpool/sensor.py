"""Support for Flexpool sensors."""
from datetime import timedelta
import logging

import async_timeout
import flexpoolapi

from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE, PERCENTAGE
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import SENSOR_DICT
from .helper import get_hashrate

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Flexpool sensors."""
    address = entry.data["address"]

    async def async_update_data():
        try:
            async with async_timeout.timeout(10):
                return await hass.async_add_executor_job(get_workers, address)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="flexpool_workers_sensor",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=SCAN_INTERVAL,
    )

    sensors = [
        FlexpoolBalanceSensor("flexpool_unpaid_balance", address),
        FlexpoolHashrateSensor("flexpool_current_reported", address),
        FlexpoolHashrateSensor("flexpool_current_effective", address),
        FlexpoolHashrateSensor("flexpool_daily_average", address),
        FlexpoolPoolHashrateSensor("flexpool_effective"),
        FlexpoolPoolWorkersSensor("flexpool_workers"),
        FlexpoolPoolLuckSensor("flexpool_luck"),
    ]

    if "workers" in entry.data:
        await coordinator.async_config_entry_first_refresh()
        await hass.async_add_executor_job(
            add_workers_sensors_loop, coordinator, async_add_entities
        )

    async_add_entities(sensors, True)


def get_workers(address):
    """Get all workers."""
    data = {}
    for worker in flexpoolapi.miner(address).workers():
        effective, reported = worker.current_hashrate()
        stats = worker.stats()
        valid = stats.valid_shares
        total = stats.valid_shares + stats.stale_shares + stats.invalid_shares

        data[worker.worker_name] = {
            "reported": reported,
            "effective": effective,
            "valid": valid,
            "total": total,
            "worker_name": worker.worker_name,
        }

    return data


def add_workers_sensors_loop(coordinator, async_add_entities):
    """Get workers and add sensors."""
    sensors = []
    for idx, worker in coordinator.data.items():
        sensors.append(
            FlexpoolWorkerHashrateSensor(
                "flexpool_worker_reported", worker["worker_name"], coordinator, idx
            )
        )
        sensors.append(
            FlexpoolWorkerHashrateSensor(
                "flexpool_worker_effective", worker["worker_name"], coordinator, idx
            )
        )
        sensors.append(
            FlexpoolWorkerShareSensor(
                "flexpool_worker_daily_valid", worker["worker_name"], coordinator, idx
            )
        )
        sensors.append(
            FlexpoolWorkerShareSensor(
                "flexpool_worker_daily_total", worker["worker_name"], coordinator, idx
            )
        )

    async_add_entities(sensors, True)


class FlexpoolBalanceSensor(Entity):
    """Representation of a flexpool unpaid balance sensor."""

    def __init__(self, name, address):
        """Initialize the sensor."""
        info = SENSOR_DICT[name]
        self._name = info[CONF_NAME]
        self._icon = info[CONF_ICON]
        self._address = address
        self._state = None
        self._unit_of_measurement = "ETH"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest state of the sensor."""
        miner = flexpoolapi.miner(self._address)
        balance = round(miner.balance() / 1000000000000000000, 4)

        self._state = balance


class FlexpoolHashrateSensor(Entity):
    """Representation of the flexpool miner hashrate sensor."""

    def __init__(self, name, address):
        """Initialize the sensor."""
        info = SENSOR_DICT[name]
        self._name = info[CONF_NAME]
        self._icon = info[CONF_ICON]
        self._type = info[CONF_TYPE]
        self._address = address
        self._state = None
        self._unit = "H/s"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of the sensor."""
        return self._unit

    def update(self):
        """Get the latest state of the sensor."""
        stats = flexpoolapi.miner(self._address).stats()

        hashrate = 0
        if self._type == "average":
            hashrate = stats.average_effective_hashrate
        elif self._type == "effective":
            hashrate = stats.current_effective_hashrate
        elif self._type == "reported":
            hashrate = stats.current_reported_hashrate

        self._state, self._unit = get_hashrate(hashrate)


class FlexpoolWorkerHashrateSensor(CoordinatorEntity, Entity):
    """Representation of a workers hashrate sensor."""

    def __init__(self, name, worker, coordinator, idx):
        """Initialize the sensor."""
        super().__init__(coordinator)
        info = SENSOR_DICT[name]
        self._idx = idx
        self._worker_name = worker
        self._icon = info[CONF_ICON]
        self._type = info[CONF_TYPE]
        self._state = None
        self._unit = "H/s"

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Flexpool {} {} Hashrate".format(
            self._worker_name, self._type.capitalize()
        )

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        worker = self.coordinator.data[self._idx]
        self._state, self._unit = get_hashrate(worker[self._type])
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of the sensor."""
        worker = self.coordinator.data[self._idx]
        self._state, self._unit = get_hashrate(worker[self._type])
        return self._unit


class FlexpoolWorkerShareSensor(CoordinatorEntity, Entity):
    """Representation of a workers shares sensor."""

    def __init__(self, name, worker, coordinator, idx):
        """Initialize the sensor."""
        super().__init__(coordinator)
        info = SENSOR_DICT[name]
        self._idx = idx
        self._worker_name = worker
        self._icon = info[CONF_ICON]
        self._type = info[CONF_TYPE]
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Flexpool {} Daily {} Shares".format(
            self._worker_name, self._type.capitalize()
        )

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self._idx][self._type]

    @property
    def unit_of_measurement(self):
        """Return the unit of the sensor."""
        return "Shares"


class FlexpoolPoolHashrateSensor(Entity):
    """Representation of a flexpool pool hashrate sensor."""

    def __init__(self, name):
        """Initialize the sensor."""
        info = SENSOR_DICT[name]
        self._name = info[CONF_NAME]
        self._icon = info[CONF_ICON]
        self._state = None
        self._unit = "H/s"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of the sensor."""
        return self._unit

    def update(self):
        """Get the latest state of the sensor."""
        hashrate = flexpoolapi.pool.hashrate()

        self._state, self._unit = get_hashrate(hashrate["total"])


class FlexpoolPoolWorkersSensor(Entity):
    """Representation of a flexpool worker count sensor."""

    def __init__(self, name):
        """Initialize the sensor."""
        info = SENSOR_DICT[name]
        self._name = info[CONF_NAME]
        self._icon = info[CONF_ICON]
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of the sensor."""
        return "Workers"

    def update(self):
        """Get the latest state of the sensor."""
        self._state = flexpoolapi.pool.workers_online()


class FlexpoolPoolLuckSensor(Entity):
    """Representation of a flexpool luck sensor."""

    def __init__(self, name):
        """Initialize the sensor."""
        info = SENSOR_DICT[name]
        self._name = info[CONF_NAME]
        self._icon = info[CONF_ICON]
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of the sensor."""
        return PERCENTAGE

    def update(self):
        """Get the latest state of the sensor."""
        self._state = round(flexpoolapi.pool.current_luck() * 100)
