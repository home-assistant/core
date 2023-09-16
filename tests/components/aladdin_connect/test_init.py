"""Test for Aladdin Connect init logic."""
from unittest.mock import MagicMock, patch

from AIOAladdinConnect.session_manager import InvalidPasswordError
from aiohttp import ClientConnectionError

from homeassistant.components.aladdin_connect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import AsyncMock, MockConfigEntry

CONFIG = {"username": "test-user", "password": "test-password"}


async def test_setup_get_doors_errors(hass: HomeAssistant) -> None:
    """Test component setup Get Doors Errors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.login",
        return_value=True,
    ), patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.get_doors",
        return_value=None,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is True
        await hass.async_block_till_done()
        assert len(hass.states.async_all()) == 0


async def test_setup_login_error(
    hass: HomeAssistant, mock_aladdinconnect_api: MagicMock
) -> None:
    """Test component setup Login Errors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)
    mock_aladdinconnect_api.login.return_value = False
    mock_aladdinconnect_api.login.side_effect = InvalidPasswordError
    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False


async def test_setup_connection_error(
    hass: HomeAssistant, mock_aladdinconnect_api: MagicMock
) -> None:
    """Test component setup Login Errors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)
    mock_aladdinconnect_api.login.side_effect = ClientConnectionError
    with patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False


async def test_setup_component_no_error(hass: HomeAssistant) -> None:
    """Test component setup No Error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.login",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_entry_password_fail(
    hass: HomeAssistant, mock_aladdinconnect_api: MagicMock
) -> None:
    """Test password fail during entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-user", "password": "test-password"},
    )
    entry.add_to_hass(hass)
    mock_aladdinconnect_api.login = AsyncMock(return_value=False)
    mock_aladdinconnect_api.login.side_effect = InvalidPasswordError
    with patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_load_and_unload(
    hass: HomeAssistant, mock_aladdinconnect_api: MagicMock
) -> None:
    """Test loading and unloading Aladdin Connect entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.aladdin_connect.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert await config_entry.async_unload(hass)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.NOT_LOADED
