"""Tests for TFA.me: test of __init__.py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from tests.common import AsyncMock, MockConfigEntry


async def test_full_entry_setup(
    hass: HomeAssistant, tfa_me_config_entry: MockConfigEntry
) -> None:
    """Test full setup of the integration."""

    config_entry = tfa_me_config_entry
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tfa_me.TFAmeUpdateCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state.name == "LOADED"

    coordinator = config_entry.runtime_data
    assert coordinator.host == "192.168.1.10"


async def test_async_unload_entry(
    hass: HomeAssistant, tfa_me_config_entry: MockConfigEntry
) -> None:
    """Test unload of the integration."""
    config_entry = tfa_me_config_entry
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tfa_me.TFAmeUpdateCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state.name == "LOADED"

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new=AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
