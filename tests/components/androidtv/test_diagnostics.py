"""Tests for the diagnostics data provided by the AndroidTV integration."""

from homeassistant.components.androidtv.diagnostics import TO_REDACT
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import patchers
from .common import CONFIG_ANDROID_DEFAULT, SHELL_RESPONSE_OFF, setup_mock_entry

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test diagnostics."""
    patch_key, _, mock_config_entry = setup_mock_entry(
        CONFIG_ANDROID_DEFAULT, MP_DOMAIN
    )
    mock_config_entry.add_to_hass(hass)

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.LOADED

    entry_dict = async_redact_data(mock_config_entry.as_dict(), TO_REDACT)
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["entry"] == entry_dict | {"discovery_keys": {}}
