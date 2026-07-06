"""Test the my-PV init."""

from unittest.mock import AsyncMock

from homeassistant.components.my_pv.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import ELWA2_SERIAL_NUMBER

from tests.common import MockConfigEntry


async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=ELWA2_SERIAL_NUMBER, data={"host": "127.0.0.1"}
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=ELWA2_SERIAL_NUMBER, data={"host": "127.0.0.1"}
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
