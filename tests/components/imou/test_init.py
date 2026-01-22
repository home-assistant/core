"""Tests for the Imou init."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.imou.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .util import CONFIG_ENTRY_DATA, async_init_integration

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
) -> None:
    """Test successful setup entry."""
    config_entry = await async_init_integration(hass)

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not None


async def test_unload_entry(
    hass: HomeAssistant,
) -> None:
    """Test successful unload entry."""
    config_entry = await async_init_integration(hass)

    assert config_entry.state is ConfigEntryState.LOADED

    unload_result = await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert unload_result is True
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
) -> None:
    """Test setup entry with authentication failure."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_ENTRY_DATA,
        unique_id=CONFIG_ENTRY_DATA["app_id"],
        entry_id="test_entry_id",
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.imou.ImouOpenApiClient",
        ) as mock_client_class,
        patch(
            "homeassistant.components.imou.ImouHaDeviceManager",
        ),
    ):
        mock_client = AsyncMock()
        mock_client.async_get_token = AsyncMock()
        mock_client_class.return_value = mock_client

        mock_coordinator = AsyncMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(
            side_effect=ConfigEntryAuthFailed("Authentication failed")
        )

        with patch(
            "homeassistant.components.imou.ImouDataUpdateCoordinator",
            return_value=mock_coordinator,
        ):
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

            # Setup should fail and return False
            assert result is False
            assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_reload_entry(
    hass: HomeAssistant,
) -> None:
    """Test reload entry."""
    config_entry = await async_init_integration(hass)

    assert config_entry.state is ConfigEntryState.LOADED

    # Reload should unload and then setup again
    # Note: async_reload_entry is registered as an update listener,
    # but hass.config_entries.async_reload directly calls async_setup_entry
    with (
        patch(
            "homeassistant.components.imou.async_unload_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.imou.async_setup_entry",
            return_value=True,
        ) as mock_setup,
        # Prevent the update listener from causing issues
        patch(
            "homeassistant.components.imou.async_reload_entry",
        ),
    ):
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert len(mock_setup.mock_calls) == 1
