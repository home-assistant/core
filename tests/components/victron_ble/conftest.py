"""Test the Victron Bluetooth Low Energy config flow."""

from collections.abc import Callable, Generator
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
def mock_config_entry_factory(
    hass: HomeAssistant,
) -> Callable[[BluetoothServiceInfo, str], MockConfigEntry]:
    """Mock config entry factory."""

    def _create_config_entry(
        service_info: BluetoothServiceInfo = VICTRON_VEBUS_SERVICE_INFO,
        access_token: str = VICTRON_VEBUS_TOKEN,
    ) -> MockConfigEntry:
        return MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_ADDRESS: service_info.address,
                CONF_ACCESS_TOKEN: access_token,
            },
            unique_id=service_info.address,
        )

    return _create_config_entry


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant, mock_config_entry_factory
) -> MockConfigEntry:
    """Mock config entry."""
    return mock_config_entry_factory()


@pytest.fixture
def mock_config_entry_added_to_hass_factory(
    mock_config_entry_factory,
    hass: HomeAssistant,
) -> Callable[[BluetoothServiceInfo, str], MockConfigEntry]:
    """Mock config entry factory that adds the entry to hass."""

    def _create_and_add_config_entry(
        service_info: BluetoothServiceInfo = VICTRON_VEBUS_SERVICE_INFO,
        access_token: str = VICTRON_VEBUS_TOKEN,
    ) -> MockConfigEntry:
        entry = mock_config_entry_factory(service_info, access_token)
        entry.add_to_hass(hass)
        return entry

    return _create_and_add_config_entry


@pytest.fixture
def mock_config_entry_added_to_hass(
    mock_config_entry_added_to_hass_factory,
) -> MockConfigEntry:
    """Mock config entry that has been added to hass."""
    return mock_config_entry_added_to_hass_factory()
