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


def setup_entry(hass, entry, add_entities, discovery_info=None):
    """Set up the Etherscan.io sensors."""
    address = entry.data["address"]
    workers = entry.data["workers"]
    poolStats = entry.data["pool"]

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
