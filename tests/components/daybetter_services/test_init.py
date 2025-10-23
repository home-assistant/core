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
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_pids",
            return_value={},
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_device_statuses",
            return_value=[],
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.close",
        ),
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state == ConfigEntryState.LOADED
        assert DOMAIN in hass.data
        assert config_entry.entry_id in hass.data[DOMAIN]
        assert "coordinator" in hass.data[DOMAIN][config_entry.entry_id]
        assert "api" in hass.data[DOMAIN][config_entry.entry_id]


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
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_pids",
            return_value={},
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_device_statuses",
            return_value=[],
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.close",
        ) as mock_close,
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state == ConfigEntryState.NOT_LOADED
        assert config_entry.entry_id not in hass.data[DOMAIN]
        mock_close.assert_called()
