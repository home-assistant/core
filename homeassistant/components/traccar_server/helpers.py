"""Helper functions for the Traccar Server integration."""

from __future__ import annotations

from pytraccar import DeviceModel, GeofenceModel, PositionModel


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


def get_geofence_ids(
    device: DeviceModel,
    position: PositionModel,
) -> list[int]:
    """Compatibility helper to return a list of geofence IDs."""
    # For Traccar >=5.8 https://github.com/traccar/traccar/commit/30bafaed42e74863c5ca68a33c87f39d1e2de93d
    if "geofenceIds" in position:
        return position["geofenceIds"] or []
    # For Traccar <5.8
    if "geofenceIds" in device:
        return device["geofenceIds"] or []
    return []
