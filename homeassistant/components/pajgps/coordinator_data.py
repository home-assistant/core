"""
CoordinatorData — immutable snapshot of all PAJ GPS data shared with entities.

This is a pure data module with no HA or network dependencies.
"""
from __future__ import annotations

import dataclasses

from pajgps_api.models.device import Device
from pajgps_api.models.trackpoint import TrackPoint
from pajgps_api.models.sensordata import SensorData
from pajgps_api.models.notification import Notification


@dataclasses.dataclass(frozen=True)
class CoordinatorData:
    """
    Typed, copy-on-write snapshot of all PAJ GPS data.

    Always replace via dataclasses.replace() — never mutate in place.
    """

    # All devices in the account (includes alarm enabled/disabled flags)
    devices: list[Device] = dataclasses.field(default_factory=list)

    # device_id → last TrackPoint
    positions: dict[int, TrackPoint] = dataclasses.field(default_factory=dict)

    # device_id → SensorData
    sensor_data: dict[int, SensorData] = dataclasses.field(default_factory=dict)

    # device_id → elevation in metres (None until first successful fetch)
    elevations: dict[int, float | None] = dataclasses.field(default_factory=dict)

    # device_id → list of unread Notification objects
    notifications: dict[int, list[Notification]] = dataclasses.field(default_factory=dict)
