"""Test the initialization of fujitsu_hvac entities."""

from unittest.mock import AsyncMock

from ayla_iot_unofficial import AylaAuthError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.fujitsu_hvac.const import API_REFRESH_SECONDS
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator_sign_in_exception_get_devices(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_devices: list[AsyncMock],
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the entities become unavailable if we fail to update them because of an auth error while getting the devices."""
    await setup_integration(hass, mock_config_entry)

    mock_ayla_api.async_get_devices.side_effect = AylaAuthError
    freezer.tick(API_REFRESH_SECONDS)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert all(e.state == STATE_UNAVAILABLE for e in hass.states.async_all())


async def test_coordinator_sign_in_exception_update_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_devices: list[AsyncMock],
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the entities become unavailable if we fail to update them because of an auth error while updating the devices."""
    await setup_integration(hass, mock_config_entry)

    for d in mock_devices:
        d.async_update.side_effect = AylaAuthError

    freezer.tick(API_REFRESH_SECONDS)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert all(e.state == STATE_UNKNOWN for e in hass.states.async_all())


async def test_coordinator_token_expired(
    hass: HomeAssistant,
    mock_devices: list[AsyncMock],
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Make sure sign_in is called if the token expired."""
    mock_ayla_api.token_expired = True
    await setup_integration(hass, mock_config_entry)

    # Called once during setup and once during update
    assert mock_ayla_api.async_sign_in.call_count == 2


async def test_coordinator_token_expiring_soon(
    hass: HomeAssistant,
    mock_devices: list[AsyncMock],
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Make sure sign_in is called if the token expired."""
    mock_ayla_api.token_expiring_soon = True
    await setup_integration(hass, mock_config_entry)

    mock_ayla_api.async_refresh_auth.assert_called_once()


@pytest.mark.parametrize("exception", [AylaAuthError, TimeoutError])
async def test_coordinator_setup_exception(
    hass: HomeAssistant,
    mock_devices: list[AsyncMock],
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Make sure that no devices is added if there was an exception while logging in."""
    mock_ayla_api.async_sign_in.side_effect = exception
    await setup_integration(hass, mock_config_entry)

    assert len(hass.states.async_all()) == 0
