"""Tests for the Anglian Water integration setup."""

from unittest.mock import AsyncMock, patch

from pyanglianwater.exceptions import ConsentRequiredError, InvalidGrantError
import pytest

from homeassistant.components.anglian_water import async_setup_entry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import ACCESS_TOKEN

from tests.common import MockConfigEntry


async def test_async_setup_entry_recovers_from_expired_refresh_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test setup retries with stored credentials when refresh grant expires."""
    mock_config_entry.add_to_hass(hass)
    mock_anglian_water_authenticator.send_refresh_request.side_effect = (
        InvalidGrantError
    )
    mock_anglian_water_authenticator.refresh_token = "new_valid_token"

    with patch.object(
        hass.config_entries, "async_forward_entry_setups", AsyncMock()
    ), patch(
        "homeassistant.components.anglian_water.coordinator."
        "AnglianWaterUpdateCoordinator.async_config_entry_first_refresh",
        AsyncMock(),
    ):
        assert await async_setup_entry(hass, mock_config_entry)

    assert mock_anglian_water_authenticator.send_login_request.await_count == 1
    assert mock_config_entry.data[CONF_ACCESS_TOKEN] == "new_valid_token"


async def test_async_setup_entry_raises_reauth_when_full_login_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anglian_water_authenticator: AsyncMock,
    mock_anglian_water_client: AsyncMock,
) -> None:
    """Test setup triggers reauth when stored credentials cannot recover."""
    mock_config_entry.add_to_hass(hass)
    mock_anglian_water_authenticator.send_refresh_request.side_effect = (
        InvalidGrantError
    )
    mock_anglian_water_authenticator.send_login_request.side_effect = (
        ConsentRequiredError
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await async_setup_entry(hass, mock_config_entry)

    assert mock_config_entry.data[CONF_ACCESS_TOKEN] == ACCESS_TOKEN
