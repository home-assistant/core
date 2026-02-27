"""Test Sharp COCORO Air integration setup and teardown."""

from unittest.mock import AsyncMock, patch

from aiosharp_cocoro_air import SharpApiError, SharpAuthError, SharpConnectionError
import pytest

from homeassistant.components.sharp_cocoro_air.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import DEVICE_1

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_sharp_api")
async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup of a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (SharpAuthError(), ConfigEntryState.SETUP_ERROR),
        (SharpConnectionError(), ConfigEntryState.SETUP_RETRY),
        (SharpApiError(), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_failure(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup failure with auth and connection errors."""
    mock_sharp_api.authenticate.side_effect = exception
    with patch(
        "homeassistant.components.sharp_cocoro_air.coordinator.asyncio.sleep",
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


@pytest.mark.usefixtures("mock_sharp_api")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_update_data_connection_error(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles connection error during data update."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    coordinator = mock_config_entry.runtime_data

    # Simulate connection error on next poll
    mock_sharp_api.get_devices.side_effect = SharpConnectionError("timeout")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_update_data_api_error(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles SharpApiError during data update."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    coordinator = mock_config_entry.runtime_data

    mock_sharp_api.get_devices.side_effect = SharpApiError("server error")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_update_data_auth_error_relogin_success(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator re-authenticates on session expiry during update."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    # First get_devices raises auth error, re-login succeeds, second call works
    mock_sharp_api.get_devices.side_effect = [
        SharpAuthError("expired"),
        [DEVICE_1],
    ]
    mock_sharp_api.authenticate.reset_mock()
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    mock_sharp_api.authenticate.assert_awaited_once()


async def test_update_data_auth_error_relogin_api_error(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles SharpApiError after re-login retry."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_sharp_api.get_devices.side_effect = [
        SharpAuthError("expired"),
        SharpApiError("server error"),
    ]
    mock_sharp_api.authenticate.reset_mock()
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    mock_sharp_api.authenticate.assert_awaited_once()


async def test_update_data_auth_error_relogin_connection_error(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles connection error after successful re-login."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    # get_devices raises auth error, re-login succeeds, retry raises connection error
    mock_sharp_api.get_devices.side_effect = [
        SharpAuthError("expired"),
        SharpConnectionError("network down"),
    ]
    mock_sharp_api.authenticate.reset_mock()
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    mock_sharp_api.authenticate.assert_awaited_once()


async def test_update_data_auth_error_relogin_fails(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator raises auth failure when re-login also fails."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_sharp_api.get_devices.side_effect = SharpAuthError("expired")
    mock_sharp_api.authenticate.side_effect = SharpAuthError("bad creds")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_control_command_auth_error(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test control command raises auth failure on session expiry."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_sharp_api.power_on.side_effect = SharpAuthError("expired")
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator.async_power_on(DEVICE_1)


async def test_control_command_connection_error(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test control command raises HomeAssistantError on connection failure."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_sharp_api.power_on.side_effect = SharpApiError("network error")
    with pytest.raises(HomeAssistantError):
        await coordinator.async_power_on(DEVICE_1)


async def test_stale_device_removal(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stale devices are removed when no longer returned by the API."""
    await setup_integration(hass, mock_config_entry)

    device_registry = dr.async_get(hass)

    # Verify both devices exist
    assert device_registry.async_get_device(identifiers={(DOMAIN, "dev1")})
    assert device_registry.async_get_device(identifiers={(DOMAIN, "dev2")})

    # Simulate device 2 being removed from API
    mock_sharp_api.get_devices.return_value = [DEVICE_1]
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Device 1 should still exist, device 2 should be removed
    assert device_registry.async_get_device(identifiers={(DOMAIN, "dev1")})
    assert not device_registry.async_get_device(identifiers={(DOMAIN, "dev2")})
