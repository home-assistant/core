"""Shared helpers and factory functions for PajGpsCoordinator tests.

Import from this module in each test file to avoid duplication.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from pajgps_api.models.device import Device
from pajgps_api.models.trackpoint import TrackPoint

from homeassistant.components.paj_gps.coordinator import PajGpsCoordinator
from homeassistant.core import HomeAssistant


def make_device(device_id: int = 1, **kwargs) -> Device:
    """Create a test Device instance with sensible defaults.

    Parameters
    ----------
    device_id : int
        The device ID, defaults to 1.
    **kwargs
        Additional keyword arguments to override defaults.

    Returns:
    -------
    Device
        A Device instance with test data.
    """
    defaults = {
        "id": device_id,
        "name": f"Device {device_id}",
        "imei": f"IMEI{device_id}",
        "modellid": 100,
        "alarmbewegung": 1,
        "alarmakkuwarnung": 1,
        "alarmsos": 1,
        "alarmgeschwindigkeit": 1,
        "alarmstromunterbrechung": 1,
        "alarmzuendalarm": 1,
        "alarm_fall_enabled": 1,
        "alarm_volt": 1,
        "device_models": [],
    }
    defaults.update(kwargs)
    return Device(**defaults)


def make_trackpoint(
    device_id: int = 1, lat: float = 52.0, lng: float = 13.0, **kwargs
) -> TrackPoint:
    """Create a test TrackPoint instance with sensible defaults.

    Parameters
    ----------
    device_id : int
        The device ID, defaults to 1.
    lat : float
        Latitude, defaults to 52.0.
    lng : float
        Longitude, defaults to 13.0.
    **kwargs
        Additional keyword arguments to override defaults.

    Returns:
    -------
    TrackPoint
        A TrackPoint instance with test data.
    """
    defaults = {
        "iddevice": device_id,
        "lat": lat,
        "lng": lng,
        "speed": 50,
        "battery": 80,
        "direction": 90,
    }
    defaults.update(kwargs)
    return TrackPoint(**defaults)


def make_entry_data(**kwargs) -> dict:
    """Create test config entry data with sensible defaults.

    Parameters
    ----------
    **kwargs
        Additional keyword arguments to override defaults.

    Returns:
    -------
    dict
        A dictionary with config entry data.
    """
    defaults = {
        "email": "test@example.com",
        "password": "secret",
    }
    defaults.update(kwargs)
    return defaults


def make_coordinator(
    hass: HomeAssistant | None = None, **entry_kwargs
) -> PajGpsCoordinator:
    """Build a coordinator with a mocked hass and mocked api.login."""
    if hass is None:
        hass = MagicMock(spec=HomeAssistant)
        hass.async_create_task = asyncio.ensure_future
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry_id"
    config_entry.data = make_entry_data(**entry_kwargs)
    with patch(
        "homeassistant.components.paj_gps.coordinator.async_get_clientsession",
        return_value=MagicMock(),
    ):
        coord = PajGpsCoordinator(hass, config_entry)
    coord.api.login = AsyncMock()
    coord._user_id = 42
    return coord
