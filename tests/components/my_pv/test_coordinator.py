"""Test the my-PV coordinator."""

from unittest.mock import AsyncMock

from my_pv.exceptions import MyPVAuthenticationError, MyPVConnectionError
import pytest

from homeassistant.components.my_pv.coordinator import MyPVCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test coordinator refresh."""
    coordinator = MyPVCoordinator(hass, mock_config_entry, mock_my_pv_client)

    await coordinator.async_refresh()
    assert coordinator.last_update_success


async def test_coordinator_refresh_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test coordinator refresh when client not connected."""
    coordinator = MyPVCoordinator(hass, mock_config_entry, mock_my_pv_client)

    await coordinator.async_refresh()
    assert coordinator.last_update_success

    mock_my_pv_client.connected = False
    mock_my_pv_client.connect.return_value = False

    await coordinator.async_refresh()

    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_coordinator_refresh_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test coordinator refresh when client has connection error."""
    coordinator = MyPVCoordinator(hass, mock_config_entry, mock_my_pv_client)

    await coordinator.async_refresh()
    assert coordinator.last_update_success

    mock_my_pv_client.connected = True
    mock_my_pv_client.fetch_data.side_effect = MyPVConnectionError()

    await coordinator.async_refresh()

    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_coordinator_refresh_fetch_data_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test coordinator refresh when client fetch data returns False."""
    coordinator = MyPVCoordinator(hass, mock_config_entry, mock_my_pv_client)

    await coordinator.async_refresh()
    assert coordinator.last_update_success

    mock_my_pv_client.connected = True
    mock_my_pv_client.fetch_data.return_value = False

    await coordinator.async_refresh()

    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_coordinator_refresh_authentication_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test coordinator refresh when client has authentication error."""
    coordinator = MyPVCoordinator(hass, mock_config_entry, mock_my_pv_client)

    await coordinator.async_refresh()
    assert coordinator.last_update_success

    mock_my_pv_client.connected = False
    mock_my_pv_client.connect.side_effect = MyPVAuthenticationError()

    await coordinator.async_refresh()

    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed)


async def test_coordinator_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test coordinator setting value."""
    coordinator = MyPVCoordinator(hass, mock_config_entry, mock_my_pv_client)

    await coordinator.async_refresh()
    assert coordinator.last_update_success

    result = await coordinator.set_target_temperature(35)
    assert result


async def test_coordinator_set_value_not_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test coordinator setting value when client not connected."""
    coordinator = MyPVCoordinator(hass, mock_config_entry, mock_my_pv_client)

    await coordinator.async_refresh()
    assert coordinator.last_update_success

    mock_my_pv_client.connected = False
    mock_my_pv_client.connect.return_value = False

    with (
        pytest.raises(HomeAssistantError),
    ):
        await coordinator.set_target_temperature(35)


async def test_coordinator_set_value_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test coordinator setting value when client has connection error."""
    coordinator = MyPVCoordinator(hass, mock_config_entry, mock_my_pv_client)

    await coordinator.async_refresh()
    assert coordinator.last_update_success

    mock_my_pv_client.connected = True
    mock_my_pv_client.set_target_temperature.side_effect = MyPVConnectionError()

    with (
        pytest.raises(HomeAssistantError),
    ):
        await coordinator.set_target_temperature(35)


async def test_coordinator_set_value_authentication_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test coordinator setting value when client has authentication error."""
    coordinator = MyPVCoordinator(hass, mock_config_entry, mock_my_pv_client)

    await coordinator.async_refresh()
    assert coordinator.last_update_success

    mock_my_pv_client.connected = False
    mock_my_pv_client.connect.side_effect = MyPVAuthenticationError()

    with (
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator.set_target_temperature(35)
