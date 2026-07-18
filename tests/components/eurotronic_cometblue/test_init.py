"""Test the Eurotronic Comet Blue integration setup."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.eurotronic_cometblue.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import FIXTURE_MAC
from .conftest import setup_with_selected_platforms

from tests.common import MockConfigEntry


async def test_device_registry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry, including the Bluetooth connection."""
    await setup_with_selected_platforms(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, FIXTURE_MAC)})
    assert device_entry == snapshot


async def test_notify_no_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test logging when no device is found."""

    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.eurotronic_cometblue.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.eurotronic_cometblue.async_address_reachability_diagnostics",
            return_value="mock reachability reason",
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "aa:bb:cc:dd:ee:ff: mock reachability reason" in caplog.text
