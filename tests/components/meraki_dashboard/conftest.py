"""Fixtures for Meraki Dashboard tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.meraki_dashboard.const import (
    CONF_INCLUDED_CLIENTS,
    CONF_NETWORK_ID,
    CONF_NETWORK_NAME,
    CONF_ORGANIZATION_ID,
    CONF_TRACK_BLUETOOTH_CLIENTS,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_INFRASTRUCTURE_DEVICES,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth_clients() -> Generator[None]:
    """Mock Bluetooth client API calls for tests by default."""
    with (
        patch(
            "homeassistant.components.meraki_dashboard.coordinator.MerakiDashboardApi.async_get_network_bluetooth_clients",
            AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.meraki_dashboard.config_flow.MerakiDashboardApi.async_get_network_bluetooth_clients",
            AsyncMock(return_value=[]),
        ),
    ):
        yield


@pytest.fixture
def mock_setup_entry() -> None:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.meraki_dashboard.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="HQ",
        data={
            CONF_API_KEY: "test-api-key",
            CONF_ORGANIZATION_ID: "1234",
            CONF_NETWORK_ID: "L_1111",
            CONF_NETWORK_NAME: "HQ",
        },
        unique_id="L_1111",
        options={
            CONF_TRACK_CLIENTS: True,
            CONF_TRACK_BLUETOOTH_CLIENTS: False,
            CONF_TRACK_INFRASTRUCTURE_DEVICES: True,
            CONF_INCLUDED_CLIENTS: [],
        },
    )
