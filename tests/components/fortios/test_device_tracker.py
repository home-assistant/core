"""Tests for the FortiOS device tracker."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.fortios.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    CONF_VERIFY_SSL,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry

MOCK_CONFIG_DATA = {
    CONF_HOST: "1.2.3.4",
    CONF_PORT: 443,
    CONF_TOKEN: "token",
    "vdom": "root",
    CONF_VERIFY_SSL: False,
}

MOCK_DEVICE = {
    "master_mac": "00:11:22:33:44:55",
    "hostname": "test_device",
    "is_online": True,
    "ipv4_address": "192.168.1.100",
    "last_seen": 1600000000,
}

MOCK_DEVICE_OFFLINE = {**MOCK_DEVICE, "is_online": False}


def _make_api_mock(device: dict | None = None) -> AsyncMock:
    """Return a mocked FortiOSAPI instance with per-endpoint responses."""
    selected_device = device or MOCK_DEVICE

    async def _get(path: str) -> dict:
        if "device/query" in path:
            return {"results": [selected_device]}
        if "resource/usage" in path:
            return {
                "results": {
                    "cpu": [{"current": 10}],
                    "mem": [{"current": 50}],
                    "session": [{"current": 100}],
                    "setuprate": [{"current": 100}],
                }
            }
        # monitor/system/status
        return {
            "version": "7.0.0",
            "serial": "FGT1234567890",
            "results": {},
        }

    mock = AsyncMock()
    mock.get.side_effect = _get
    return mock


def _patch_api(device: dict | None = None):
    """Patch FortiOSAPI with a mock returning appropriate per-endpoint data."""
    return patch(
        "homeassistant.components.fortios.FortiOSAPI",
        return_value=_make_api_mock(device),
    )


@pytest.fixture
def mock_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create and register a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="FGT1234567890",
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_home(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Test that an online device is in STATE_HOME."""
    with _patch_api():
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test_device")
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["mac"] == "00:11:22:33:44:55"
    assert state.attributes["ip"] == "192.168.1.100"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_not_home(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Test that an offline device transitions to STATE_NOT_HOME."""
    with _patch_api():
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_entry.runtime_data
    coordinator.api.get.side_effect = _make_api_mock(
        MOCK_DEVICE_OFFLINE
    ).get.side_effect
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test_device")
    assert state is not None
    assert state.state == STATE_NOT_HOME


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_extra_attributes(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Test that extra state attributes use snake_case keys."""
    device_with_extras = {
        **MOCK_DEVICE,
        "os_name": "Android",
        "os_version": "12",
        "hardware_vendor": "Samsung",
        "hardware_type": "smartphone",
        "hardware_family": "smartphone",
        "hardware_version": "1.0",
        "ipv6_address": "",
    }

    with _patch_api(device=device_with_extras):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("device_tracker.test_device")
    assert state is not None
    assert state.attributes["os_name"] == "Android"
    assert state.attributes["os_version"] == "12"
    assert state.attributes["hardware_vendor"] == "Samsung"
    assert state.attributes["hardware_type"] == "smartphone"
    # Ensure old-style keys with capitals/spaces are NOT present
    assert "OS_name" not in state.attributes
    assert "Hardware vendor" not in state.attributes


async def test_coordinator_update_failed(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Test that UpdateFailed is raised when the API call fails."""
    with _patch_api():
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_entry.runtime_data
    # Replace the api with one that raises an exception
    coordinator.api.get.side_effect = Exception("API Error")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
