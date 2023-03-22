"""Test BMW diagnostics."""
import datetime
import json
import os
import time

from freezegun import freeze_time

from homeassistant.components.bmw_connected_drive.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_mocked_integration

from tests.common import load_fixture
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


@freeze_time(datetime.datetime(2022, 7, 10, 11))
async def test_config_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, bmw_fixture
) -> None:
    """Test config entry diagnostics."""

    # Make sure that local timezone for test is UTC
    os.environ["TZ"] = "UTC"
    time.tzset()

    mock_config_entry = await setup_mocked_integration(hass)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    diagnostics_fixture = json.loads(
        load_fixture("diagnostics/diagnostics_config_entry.json", DOMAIN)
    )

    assert diagnostics == diagnostics_fixture


@freeze_time(datetime.datetime(2022, 7, 10, 11))
async def test_device_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, bmw_fixture
) -> None:
    """Test device diagnostics."""

    # Make sure that local timezone for test is UTC
    os.environ["TZ"] = "UTC"
    time.tzset()

    mock_config_entry = await setup_mocked_integration(hass)

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "WBY00000000REXI01")},
    )
    assert reg_device is not None

    diagnostics = await get_diagnostics_for_device(
        hass, hass_client, mock_config_entry, reg_device
    )

    diagnostics_fixture = json.loads(
        load_fixture("diagnostics/diagnostics_device.json", DOMAIN)
    )

    assert diagnostics == diagnostics_fixture


@freeze_time(datetime.datetime(2022, 7, 10, 11))
async def test_device_diagnostics_vehicle_not_found(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, bmw_fixture
) -> None:
    """Test device diagnostics when the vehicle cannot be found."""

    # Make sure that local timezone for test is UTC
    os.environ["TZ"] = "UTC"
    time.tzset()

    mock_config_entry = await setup_mocked_integration(hass)

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "WBY00000000REXI01")},
    )
    assert reg_device is not None

    # Change vehicle identifier so that vehicle will not be found
    device_registry.async_update_device(
        reg_device.id, new_identifiers={(DOMAIN, "WBY00000000REXI99")}
    )

    diagnostics = await get_diagnostics_for_device(
        hass, hass_client, mock_config_entry, reg_device
    )

    diagnostics_fixture = json.loads(
        load_fixture("diagnostics/diagnostics_device.json", DOMAIN)
    )
    # Mock empty data if car is not found in account anymore
    diagnostics_fixture["data"] = None

    assert diagnostics == diagnostics_fixture
