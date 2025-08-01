"""Test the Victron Bluetooth Low Energy config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.victron_ble.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .fixtures import VICTRON_VEBUS_SERVICE_INFO, VICTRON_VEBUS_TOKEN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.victron_ble.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_discovered_service_info() -> Generator[AsyncMock]:
    """Mock discovered service info."""
    with patch(
        "homeassistant.components.victron_ble.config_flow.async_discovered_service_info",
        return_value=[VICTRON_VEBUS_SERVICE_INFO],
    ) as mock_discovered_service_info:
        yield mock_discovered_service_info


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a config entry for testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: VICTRON_VEBUS_SERVICE_INFO.address,
            CONF_ACCESS_TOKEN: VICTRON_VEBUS_TOKEN,
        },
        unique_id=VICTRON_VEBUS_SERVICE_INFO.address,
    )


@pytest.fixture
def mock_config_entry_added_to_hass(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Add the mock config entry to hass."""
    mock_config_entry.add_to_hass(hass)
