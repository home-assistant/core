"""Test Subaru diagnostics."""
import json
from unittest.mock import patch

import pytest

from homeassistant.components.subaru.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .api_responses import TEST_VIN_2_EV
from .conftest import MOCK_API_FETCH, MOCK_API_GET_DATA, advance_time_to_next_fetch

from tests.common import load_fixture
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


async def test_config_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, ev_entry
) -> None:
    """Test config entry diagnostics."""

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    diagnostics_fixture = json.loads(
        load_fixture("subaru/diagnostics_config_entry.json")
    )

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == diagnostics_fixture
    )


async def test_device_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, ev_entry
) -> None:
    """Test device diagnostics."""

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_VIN_2_EV)},
    )
    assert reg_device is not None

    diagnostics_fixture = json.loads(load_fixture("subaru/diagnostics_device.json"))

    assert (
        await get_diagnostics_for_device(hass, hass_client, config_entry, reg_device)
        == diagnostics_fixture
    )


async def test_device_diagnostics_vehicle_not_found(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, ev_entry
) -> None:
    """Test device diagnostics when the vehicle cannot be found."""

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_VIN_2_EV)},
    )
    assert reg_device is not None

    # Simulate case where Subaru API does not return vehicle data
    with patch(MOCK_API_FETCH), patch(MOCK_API_GET_DATA, return_value=None):
        advance_time_to_next_fetch(hass)
        await hass.async_block_till_done()

    with pytest.raises(AssertionError):
        await get_diagnostics_for_device(hass, hass_client, config_entry, reg_device)
