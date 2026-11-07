"""Tests for the Gree Climate diagnostics."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.gree.const import DOMAIN
from homeassistant.components.gree.discovery import device_info_to_data
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import async_setup_gree, build_device_info_mock


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    mock_device = device.return_value
    mock_device.device_info.brand = "gree"
    mock_device.device_info.model = "gree"
    mock_device.device_info.version = "V1.2.1"
    mock_device.hid = "362001000762+U-CS532AE(LT)V3.31.bin"
    mock_device.version = "3.31"
    mock_device.raw_properties = {
        "Pow": 1,
        "Mod": 1,
        "SetTem": 22,
        "TemSen": 64,
        "TemUn": 0,
        "WdSpd": 0,
        "Lig": 1,
        "Quiet": 0,
        "Tur": 0,
    }

    entry = await async_setup_gree(hass)

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot


@pytest.mark.parametrize(
    ("entry", "expected_state"),
    [
        pytest.param(
            MockConfigEntry(domain=DOMAIN, version=1, unique_id="gree"),
            ConfigEntryState.LOADED,
            id="empty-legacy",
        ),
        pytest.param(
            MockConfigEntry(
                domain=DOMAIN,
                version=2,
                minor_version=1,
                unique_id="aabbcc112233",
                data={**device_info_to_data(build_device_info_mock()), CONF_HOST: None},
            ),
            ConfigEntryState.SETUP_RETRY,
            id="hostless",
        ),
    ],
)
async def test_entry_diagnostics_without_coordinator(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    discovery: MagicMock,
    entry: MockConfigEntry,
    expected_state: ConfigEntryState,
) -> None:
    """Entries retained without a device connection still offer diagnostics."""
    discovery.mock_devices.clear()
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is expected_state

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == {
        "devices": []
    }
