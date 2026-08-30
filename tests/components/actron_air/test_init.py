"""Tests for the Actron Air integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from actron_neo_api import ActronAirAPIError, ActronAirAuthError
import pytest

from homeassistant.components.actron_air.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_actron_api")
async def test_setup_entry_uses_shared_session(
    hass: HomeAssistant,
    mock_actron_api_class: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the API is created with Home Assistant's shared client session."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_actron_api_class.call_args.kwargs["session"] is async_get_clientsession(
        hass
    )


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry raises ConfigEntryAuthFailed on auth error."""
    mock_actron_api.get_ac_systems.side_effect = ActronAirAuthError("Auth failed")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_api_error(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry raises ConfigEntryNotReady on API error."""
    mock_actron_api.get_ac_systems.side_effect = ActronAirAPIError("API failed")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_start_push_auth_error(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry raises ConfigEntryAuthFailed when starting push fails."""
    mock_actron_api.start_push.side_effect = ActronAirAuthError("Auth failed")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    ("push_enabled", "expected_stop_push_calls"),
    [
        pytest.param(True, 1, id="push_enabled"),
        pytest.param(False, 0, id="push_unavailable"),
    ],
)
async def test_unload_entry_stops_push(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    push_enabled: bool,
    expected_stop_push_calls: int,
) -> None:
    """Test push is only stopped on unload when it was started."""
    mock_actron_api.start_push.return_value = push_enabled

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_actron_api.stop_push.call_count == expected_stop_push_calls


@pytest.mark.parametrize(
    "identifier",
    [
        pytest.param("123456_zone_0", id="zone"),
        pytest.param("PERIPH001", id="peripheral"),
    ],
)
async def test_device_via_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_actron_api: AsyncMock,
    mock_zone: MagicMock,
    identifier: str,
) -> None:
    """Test zone and peripheral devices link to the AC system device."""
    mock_actron_api.state_manager.get_status.return_value.remote_zone_info = [mock_zone]

    with patch(
        "homeassistant.components.actron_air.PLATFORMS",
        [Platform.CLIMATE, Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    system_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "123456"), mock_config_entry.entry_id
    )
    assert system_device is not None

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, identifier), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.via_device_id == system_device.id
