"""Tests for TFA.me: test of __init__.py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.tfa_me import async_unload_entry
from homeassistant.components.tfa_me.const import CONF_NAME_WITH_STATION_ID, DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def mock_config_entryX() -> MockConfigEntry:
    """Fixture for a MockConfigEntry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_NAME_WITH_STATION_ID: True,
        },
        entry_id="1234",
        unique_id="unique_1234",
    )


@pytest.mark.asyncio
async def test_full_entry_setup(hass: HomeAssistant) -> None:
    """Test full setup of the integration."""
    mock_config_entry = mock_config_entryX()
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tfa_me.TFAmeDataCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(return_value=True),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Now state is LOADED
    assert mock_config_entry.state.name == "LOADED"
    # assert mock_config_entry.entry_id in hass.data[DOMAIN]

    # Asserts
    coordinator = mock_config_entry.runtime_data
    assert coordinator.host == "127.0.0.1"


@pytest.mark.asyncio
async def test_async_unload_entry(hass: HomeAssistant) -> None:
    """Test unload of the integration."""
    mock_config_entry = mock_config_entryX()
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tfa_me.TFAmeDataCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(return_value=True),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Now state is LOADED
    assert mock_config_entry.state.name == "LOADED"

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        new=AsyncMock(return_value=True),
    ):
        result = await async_unload_entry(hass, mock_config_entry)
        await hass.async_block_till_done()

    assert result is True
