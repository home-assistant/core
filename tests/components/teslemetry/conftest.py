"""Fixtures for Teslemetry."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.teslemetry.const import DOMAIN

from .const import COMMAND_SUCCESS, CONFIG, WAKE_AWAKE

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture(autouse=False)
def teslemetry_mock():
    """Mock Teslemetry api class."""
    with patch(
        "homeassistant.components.teslemetry.Teslemetry",
    ) as teslemetry_mock:
        teslemetry_mock.return_value.products = AsyncMock(
            return_value=load_json_object_fixture("products.json", DOMAIN)
        )
        teslemetry_mock.return_value.test = AsyncMock(return_value=True)
        yield teslemetry_mock


@pytest.fixture(autouse=False)
def teslemetry_vehicle_specific_mock():
    """Mock Teslemetry VehicleSpecific subclass."""
    with patch(
        "homeassistant.components.teslemetry.Teslemetry.VehicleSpecific",
    ) as vehicle_specific_mock:
        vehicle_specific_mock.return_value.wake_up = AsyncMock(return_value=WAKE_AWAKE)
        vehicle_specific_mock.return_value.vehicle_data = AsyncMock(
            return_value=load_json_object_fixture("vehicle_data.json", DOMAIN)
        )
        vehicle_specific_mock.return_value.auto_conditioning_start = AsyncMock(
            return_value=COMMAND_SUCCESS
        )
        vehicle_specific_mock.return_value.auto_conditioning_stop = AsyncMock(
            return_value=COMMAND_SUCCESS
        )
        vehicle_specific_mock.return_value.set_temps = AsyncMock(
            return_value=COMMAND_SUCCESS
        )
        vehicle_specific_mock.return_value.set_climate_keeper_mode = AsyncMock(
            return_value=COMMAND_SUCCESS
        )

        yield vehicle_specific_mock


@pytest.fixture(autouse=True)
def config_entry_mock():
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
    )
