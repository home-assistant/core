"""Test the init file code."""

from unittest.mock import patch

from zeversolar import ZeverSolarData
from zeversolar.exceptions import ZeverSolarTimeout

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry_fails(
    hass: HomeAssistant, config_entry: MockConfigEntry, zeversolar_data: ZeverSolarData
) -> None:
    """Test to load/unload the integration."""

    config_entry.add_to_hass(hass)

    with (
        patch("zeversolar.ZeverSolarClient.get_data", side_effect=ZeverSolarTimeout),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    with (
        patch("homeassistant.components.zeversolar.PLATFORMS", []),
        patch("zeversolar.ZeverSolarClient.get_data", return_value=zeversolar_data),
    ):
        hass.config_entries.async_schedule_reload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    with (
        patch("homeassistant.components.zeversolar.PLATFORMS", []),
    ):
        result = await hass.config_entries.async_unload(config_entry.entry_id)
    assert result is True
    assert config_entry.state is ConfigEntryState.NOT_LOADED
