"""Fixtures for the Fully Kiosk Browser integration tests."""

from __future__ import annotations

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.fully_kiosk.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Test device",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "mocked-password",
            CONF_MAC: "aa:bb:cc:dd:ee:ff",
            CONF_SSL: False,
            CONF_VERIFY_SSL: False,
        },
        unique_id="12345",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.fully_kiosk.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_fully_kiosk_config_flow() -> Generator[MagicMock]:
    """Return a mocked Fully Kiosk client for the config flow."""
    with patch(
        "homeassistant.components.fully_kiosk.config_flow.FullyKiosk",
        autospec=True,
    ) as client_mock:
        client = client_mock.return_value
        client.getDeviceInfo.return_value = {
            "deviceName": "Test device",
            "deviceID": "12345",
            "Mac": "AA:BB:CC:DD:EE:FF",
        }
        yield client


@pytest.fixture
def mock_fully_kiosk() -> Generator[MagicMock]:
    """Return a mocked Fully Kiosk client."""
    with patch(
        "homeassistant.components.fully_kiosk.coordinator.FullyKiosk",
        autospec=True,
    ) as client_mock:
        client = client_mock.return_value
        client.getDeviceInfo.return_value = json.loads(
            load_fixture("deviceinfo.json", DOMAIN)
        )
        client.getSettings.return_value = json.loads(
            load_fixture("listsettings.json", DOMAIN)
        )
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_fully_kiosk: MagicMock
) -> MockConfigEntry:
    """Set up the Fully Kiosk Browser integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
