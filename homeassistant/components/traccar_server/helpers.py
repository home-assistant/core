"""Helper functions for the Traccar Server integration."""
from __future__ import annotations

from pytraccar import DeviceModel, GeofenceModel


def get_device(device_id: int, devices: list[DeviceModel]) -> DeviceModel | None:
    """Return the device."""
    return next(
        (dev for dev in devices if dev["id"] == device_id),
        None,
    )


def get_first_geofence(
    geofences: list[GeofenceModel],
    target: list[int],
) -> GeofenceModel | None:
    """Return the geofence."""
    return next(
        (geofence for geofence in geofences if geofence["id"] in target),
        None,
    )
