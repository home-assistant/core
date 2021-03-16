"""Support for Etherscan sensors."""
from datetime import timedelta

import flexpoolapi

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


async def async_setup_entry(hass, entry, async_add_entities, discovery_info=None):
    """Set up the Etherscan.io sensors."""
    address = entry.data["address"]

    sensors = [
        FlexpoolBalanceSensor("flexpool_unpaid_balance", address),
        FlexpoolHashrateSensor("flexpool_current_reported", address),
        FlexpoolHashrateSensor("flexpool_current_effective", address),
        FlexpoolHashrateSensor("flexpool_daily_average", address),
    ]

    if "workers" in entry.data:
        await hass.async_add_executor_job(
            add_workers_sensors_loop, address, async_add_entities
        )

    if "pool" in entry.data:
        sensors.append(FlexpoolPoolHashrateSensor("flexpool_effective"))
        sensors.append(FlexpoolPoolWorkersSensor("flexpool_workers"))
        sensors.append(FlexpoolPoolLuckSensor("flexpool_luck"))

    async_add_entities(sensors, True)


def add_workers_sensors_loop(address, async_add_entities):
    """Get workers and add sensors."""
    sensors = []
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

    async_add_entities(sensors, True)
