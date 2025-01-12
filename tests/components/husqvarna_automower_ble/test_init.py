"""Test the Husqvarna Automower Bluetooth setup."""

from unittest.mock import Mock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.husqvarna_automower_ble.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import AUTOMOWER_SERVICE_INFO

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_automower_client")


async def test_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected devices."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{AUTOMOWER_SERVICE_INFO.address}_1197489078")}
    )

    assert device_entry == snapshot


async def test_setup_failed_connect(
    hass: HomeAssistant,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup creates expected devices."""

    mock_automower_client.connect.side_effect = TimeoutError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_invalid_pin(
    hass: HomeAssistant,
    mock_automower_client: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unable to connect, usually due to incorrect PIN."""
    mock_automower_client.connect.return_value = False

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"

    hass.config_entries.flow.async_abort(flows[0]["flow_id"])
    assert not hass.config_entries.flow.async_progress()
