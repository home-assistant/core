"""Support for Etherscan sensors."""
from datetime import timedelta

import flexpoolapi
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_ADDRESS, CONF_DEVICES, CONF_SERVICE_DATA
import homeassistant.helpers.config_validation as cv

from .sensors import (
    FlexpoolBalanceSensor,
    FlexpoolHashrateSensor,
    FlexpoolPoolHashrateSensor,
    FlexpoolPoolLuckSensor,
    FlexpoolPoolWorkersSensor,
    FlexpoolWorkerHashrateSensor,
    FlexpoolWorkerShareSensor,
)

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Optional(CONF_DEVICES): cv.boolean,
        vol.Optional(CONF_SERVICE_DATA): cv.boolean,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Etherscan.io sensors."""
    address = config.get(CONF_ADDRESS)
    workers = config.get(CONF_DEVICES)
    poolStats = config.get(CONF_SERVICE_DATA)

    sensors = [
        FlexpoolBalanceSensor("flexpool_unpaid_balance", address),
        FlexpoolHashrateSensor("flexpool_current_reported", address),
        FlexpoolHashrateSensor("flexpool_current_effective", address),
        FlexpoolHashrateSensor("flexpool_daily_average", address),
    ]

    if workers:
        workers = flexpoolapi.miner(address).workers()
        for worker in workers:
            sensors.append(
                FlexpoolWorkerHashrateSensor(
                    "flexpool_worker_reported", address, worker.worker_name
                )
            )
            sensors.append(
                FlexpoolWorkerHashrateSensor(
                    "flexpool_worker_effective", address, worker.worker_name
                )
            )
            sensors.append(
                FlexpoolWorkerShareSensor(
                    "flexpool_worker_daily_valid", address, worker.worker_name
                )
            )
            sensors.append(
                FlexpoolWorkerShareSensor(
                    "flexpool_worker_daily_total", address, worker.worker_name
                )
            )

    if poolStats:
        sensors.append(FlexpoolPoolHashrateSensor("flexpool_effective"))
        sensors.append(FlexpoolPoolWorkersSensor("flexpool_workers"))
        sensors.append(FlexpoolPoolLuckSensor("flexpool_luck"))

    add_entities(sensors, True)
