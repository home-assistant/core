"""Tests for the Actron Air integration setup."""

from unittest.mock import AsyncMock

from actron_neo_api import ActronAirAPIError, ActronAirAuthError
import pytest

from homeassistant.components.actron_air.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


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


@pytest.mark.usefixtures("init_integration_with_zone")
async def test_zone_device_via_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the zone device links to the AC system device via via_device_id."""
    system_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "123456"), mock_config_entry.entry_id
    )
    assert system_device is not None

    zone_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "123456_zone_0"), mock_config_entry.entry_id
    )
    assert zone_device is not None
    assert zone_device.via_device_id == system_device.id
