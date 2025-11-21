"""Test the Victron Bluetooth Low Energy config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from home_assistant_bluetooth import BluetoothServiceInfo
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
def service_info() -> BluetoothServiceInfo:
    """Return service info."""
    return VICTRON_VEBUS_SERVICE_INFO


@pytest.fixture
def access_token() -> str:
    """Return access token."""
    return VICTRON_VEBUS_TOKEN


@pytest.fixture
def mock_config_entry(
    service_info: BluetoothServiceInfo, access_token: str
) -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: service_info.address,
            CONF_ACCESS_TOKEN: access_token,
        },
        unique_id=service_info.address,
    )


@pytest.fixture
def mock_config_entry_added_to_hass(
    mock_config_entry,
    hass: HomeAssistant,
    service_info: BluetoothServiceInfo,
    access_token: str,
) -> MockConfigEntry:
    """Mock config entry factory that added to hass."""

    entry = mock_config_entry
    entry.add_to_hass(hass)
    return entry
