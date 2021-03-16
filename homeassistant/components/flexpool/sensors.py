"""Sensor classes for the Flexpool integration."""
import flexpoolapi

from homeassistant.const import PERCENTAGE
from homeassistant.helpers.entity import Entity

from .const import SENSOR_DICT
from .helper import get_hashrate


class FlexpoolBalanceSensor(Entity):
    """Representation of an Etherscan.io sensor."""

    def __init__(self, name, address):
        """Initialize the sensor."""
        info = SENSOR_DICT[name]
        self._name = info[0]
        self._icon = info[1]
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
    """Representation of an Etherscan.io sensor."""

    def __init__(self, name, address):
        """Initialize the sensor."""
        info = SENSOR_DICT[name]
        self._name = info[0]
        self._icon = info[1]
        self._type = info[2]
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


class FlexpoolWorkerHashrateSensor(Entity):
    """Representation of an Etherscan.io sensor."""

    def __init__(self, name, address, worker):
        """Initialize the sensor."""
        info = SENSOR_DICT[name]
        self._worker_name = worker
        self._icon = info[1]
        self._type = info[2]
        self._address = address
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
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of the sensor."""
        return self._unit

    def update(self):
        """Get the latest state of the sensor."""
        workers = flexpoolapi.miner(self._address).workers()

        hashrate = 0
        # Ugly but I don't think there is another way
        for worker in workers:
            if worker.worker_name != self._worker_name:
                continue

            if self._type == "effective":
                hashrate, _ = worker.current_hashrate()
            elif self._type == "reported":
                _, hashrate = worker.current_hashrate()

            break

        self._state, self._unit = get_hashrate(hashrate)


class FlexpoolWorkerShareSensor(Entity):
    """Representation of an Etherscan.io sensor."""

    def __init__(self, name, address, worker):
        """Initialize the sensor."""
        info = SENSOR_DICT[name]
        self._worker_name = worker
        self._icon = info[1]
        self._type = info[2]
        self._address = address
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
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of the sensor."""
        return "Shares"

    def update(self):
        """Get the latest state of the sensor."""
        workers = flexpoolapi.miner(self._address).workers()

        shares = 0
        # Ugly but I don't think there is another way
        for worker in workers:
            if worker.worker_name != self._worker_name:
                continue

            if self._type == "total":
                stats = worker.stats()
                shares = stats.valid_shares + stats.stale_shares + stats.invalid_shares
            elif self._type == "valid":
                shares = worker.stats().valid_shares

            break

        self._state = shares


class FlexpoolPoolHashrateSensor(Entity):
    """Representation of an Etherscan.io sensor."""

    def __init__(self, name):
        """Initialize the sensor."""
        info = SENSOR_DICT[name]
        self._name = info[0]
        self._icon = info[1]
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
    """Representation of an Etherscan.io sensor."""

    def __init__(self, name):
        """Initialize the sensor."""
        info = SENSOR_DICT[name]
        self._name = info[0]
        self._icon = info[1]
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
    """Representation of an Etherscan.io sensor."""

    def __init__(self, name):
        """Initialize the sensor."""
        info = SENSOR_DICT[name]
        self._name = info[0]
        self._icon = info[1]
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
