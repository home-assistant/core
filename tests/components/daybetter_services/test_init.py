"""Test the DayBetter Services init."""

from unittest.mock import patch

from homeassistant.components.daybetter_services.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": "test_token"},
    )

    with (
        patch(
            "homeassistant.components.daybetter_services.DayBetterClient.fetch_sensor_data",
            return_value=[],
        ),
        patch(
            "homeassistant.components.daybetter_services.DayBetterClient.close",
        ),
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state == ConfigEntryState.LOADED


async def test_async_setup_entry_no_token(hass: HomeAssistant) -> None:
    """Test async_setup_entry with no token."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="DayBetter Services",
        data={},  # No token
        entry_id="test_no_token",
    )
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_async_unload_entry(hass: HomeAssistant) -> None:
    """Test async_unload_entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"token": "test_token"},
    )

    with (
        patch(
            "homeassistant.components.daybetter_services.DayBetterClient.fetch_sensor_data",
            return_value=[],
        ),
        patch(
            "homeassistant.components.daybetter_services.DayBetterClient.close",
        ) as mock_close,
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state == ConfigEntryState.NOT_LOADED
        mock_close.assert_called()
