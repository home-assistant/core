"""Tests for AndroidTV integration initialization."""

from homeassistant.components.androidtv.const import (
    CONF_SCREENCAP,
    CONF_SCREENCAP_INTERVAL,
)
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.core import HomeAssistant

from . import patchers
from .common import CONFIG_ANDROID_DEFAULT, SHELL_RESPONSE_OFF, setup_mock_entry


async def test_migrate_version(
    hass: HomeAssistant,
) -> None:
    """Test migration to new version."""
    patch_key, _, mock_config_entry = setup_mock_entry(
        CONFIG_ANDROID_DEFAULT,
        MP_DOMAIN,
        options={CONF_SCREENCAP: False},
        minor_version=1,
    )
    mock_config_entry.add_to_hass(hass)

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.options[CONF_SCREENCAP_INTERVAL] == 0
        assert mock_config_entry.minor_version == 2
