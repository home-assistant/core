"""Test Subaru diagnostics."""

import json
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.subaru.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .api_responses import TEST_VIN_2_EV
from .conftest import (
    MOCK_API_FETCH,
    MOCK_API_GET_DATA,
    MOCK_API_GET_RAW_DATA,
    advance_time_to_next_fetch,
)

from tests.common import load_fixture
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    ev_entry,
) -> None:
    """Test config entry diagnostics."""

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )


async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    ev_entry,
) -> None:
    """Test device diagnostics."""

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_VIN_2_EV)},
    )
    assert reg_device is not None

    raw_data = json.loads(load_fixture("subaru/raw_api_data.json"))
    with patch(MOCK_API_GET_RAW_DATA, return_value=raw_data) as mock_get_raw_data:
        assert (
            await get_diagnostics_for_device(
                hass, hass_client, config_entry, reg_device
            )
            == snapshot
        )
        mock_get_raw_data.assert_called_once()


async def test_device_diagnostics_vehicle_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    ev_entry,
) -> None:
    """Test device diagnostics when the vehicle cannot be found."""

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

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
