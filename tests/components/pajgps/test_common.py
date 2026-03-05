"""
Shared helpers and factory functions for PajGpsCoordinator tests.
Import from this module in each test file to avoid duplication.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from pajgps_api.models.device import Device
from pajgps_api.models.trackpoint import TrackPoint
from pajgps_api.models.sensordata import SensorData
from pajgps_api.models.notification import Notification

from homeassistant.components.pajgps.coordinator import PajGpsCoordinator
from homeassistant.components.pajgps.coordinator_data import CoordinatorData


from homeassistant.components.pajgps.const import ALERT_TYPE_TO_MODEL_FIELD


# A device_models entry that advertises support for every known alert type,
# plus a model name so get_device_info can read device_models[0]["model"].
ALL_ALERTS_MODEL = {"model": "Test Model", **{model_field: 1 for model_field in ALERT_TYPE_TO_MODEL_FIELD.values()}}


def make_device(device_id: int = 1, **kwargs) -> Device:
    defaults = dict(
        id=device_id,
        name=f"Device {device_id}",
        imei=f"IMEI{device_id}",
        modellid=100,
        alarmbewegung=1,
        alarmakkuwarnung=1,
        alarmsos=1,
        alarmgeschwindigkeit=1,
        alarmstromunterbrechung=1,
        alarmzuendalarm=1,
        alarm_fall_enabled=1,
        alarm_volt=1,
        device_models=[dict(ALL_ALERTS_MODEL)],
    )
    defaults.update(kwargs)
    return Device(**defaults)


def make_trackpoint(device_id: int = 1, lat: float = 52.0, lng: float = 13.0, **kwargs) -> TrackPoint:
    defaults = dict(iddevice=device_id, lat=lat, lng=lng, speed=50, battery=80, direction=90)
    defaults.update(kwargs)
    return TrackPoint(**defaults)


def make_sensor(device_id: int = 1, volt: int = 12) -> SensorData:
    return SensorData(volt=volt, did=device_id)


def make_notification(device_id: int = 1, alert_type: int = 2, is_read: int = 0) -> Notification:
    return Notification(
        id=1, iddevice=device_id, icon="", bezeichnung="", meldungtyp=alert_type,
        dateunix=0, lat=52.0, lng=13.0, isread=is_read,
        radiusin=0, radiusout=0, zuendon=0, zuendoff=0, push=0, suppressed=0,
    )


def make_entry_data(**kwargs) -> dict:
    defaults = dict(
        guid="test-guid",
        entry_name="Test Entry",
        email="test@example.com",
        password="secret",
        mark_alerts_as_read=False,
        fetch_elevation=False,
        force_battery=False,
    )
    defaults.update(kwargs)
    return defaults


def make_coordinator(hass=None, **entry_kwargs) -> PajGpsCoordinator:
    """Build a coordinator with a mocked hass and mocked api.login."""
    if hass is None:
        hass = MagicMock()
        hass.async_create_task = lambda coro: asyncio.ensure_future(coro)
    coord = PajGpsCoordinator(hass, make_entry_data(**entry_kwargs))
    coord.api.login = AsyncMock()
    return coord
