"""Test fixtures for Wibeee integration."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pywibeee import WibeeeDeviceInfo

from homeassistant.components.wibeee.const import (
    CONF_MAC_ADDRESS,
    CONF_WIBEEE_ID,
    DOMAIN,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture

MOCK_HOST = "192.168.1.100"
MOCK_MAC = "001ec0112233"
MOCK_WIBEEE_ID = "WIBEEE"
MOCK_MODEL = "WBT"
MOCK_FIRMWARE = "4.4.199"

EXPECTED_DATA = {
    CONF_HOST: MOCK_HOST,
    CONF_MAC_ADDRESS: MOCK_MAC,
    CONF_WIBEEE_ID: MOCK_WIBEEE_ID,
}


def build_device_info() -> WibeeeDeviceInfo:
    """Return a mock Wibeee device info object."""
    return WibeeeDeviceInfo(
        wibeee_id=MOCK_WIBEEE_ID,
        mac_addr=MOCK_MAC,
        model=MOCK_MODEL,
        firmware_version=MOCK_FIRMWARE,
        ip_addr=MOCK_HOST,
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_MAC,
        title="Wibeee 112233",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_MAC_ADDRESS: MOCK_MAC,
            CONF_WIBEEE_ID: MOCK_WIBEEE_ID,
        },
        options={},
        version=1,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.wibeee.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_wibeee_api() -> Generator[AsyncMock]:
    """Mock a Wibeee API client."""
    with (
        patch(
            "homeassistant.components.wibeee.coordinator.WibeeeAPI",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.wibeee.config_flow.WibeeeAPI",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.host = MOCK_HOST
        client.async_check_connection.return_value = True
        client.async_fetch_device_info.return_value = build_device_info()
        client.async_fetch_sensors_data.return_value = load_json_object_fixture(
            "sensors_data.json", DOMAIN
        )
        client.async_fetch_status.return_value = {
            "model": MOCK_MODEL,
            "webversion": MOCK_FIRMWARE,
        }
        yield client


@pytest.fixture(name="loaded_entry")
async def load_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wibeee_api: AsyncMock,
) -> MockConfigEntry:
    """Set up the Wibeee integration in Home Assistant."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
