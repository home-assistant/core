"""Test BMW diagnostics."""
import datetime
import os
import time

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bmw_connected_drive.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_mocked_integration

from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


@pytest.mark.freeze_time(datetime.datetime(2022, 7, 10, 11))
async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    bmw_fixture,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""

    # Make sure that local timezone for test is UTC
    os.environ["TZ"] = "UTC"
    time.tzset()

    mock_config_entry = await setup_mocked_integration(hass)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics == snapshot


@pytest.mark.freeze_time(datetime.datetime(2022, 7, 10, 11))
async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    bmw_fixture,
    snapshot: SnapshotAssertion,
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

    assert diagnostics == snapshot


@pytest.mark.freeze_time(datetime.datetime(2022, 7, 10, 11))
async def test_device_diagnostics_vehicle_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    bmw_fixture,
    snapshot: SnapshotAssertion,
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

    assert diagnostics == snapshot
