"""The tests for the Canary component."""
from unittest.mock import patch

from requests import ConnectTimeout

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.canary.const import CONF_FFMPEG_ARGUMENTS, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import YAML_CONFIG, init_integration


async def test_import_from_yaml(hass: HomeAssistant, canary) -> None:
    """Test import from YAML."""
    with patch(
        "homeassistant.components.canary.async_setup_entry",
        return_value=True,
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: YAML_CONFIG})
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert entries[0].data[CONF_USERNAME] == "test-username"
    assert entries[0].data[CONF_PASSWORD] == "test-password"
    assert entries[0].data[CONF_TIMEOUT] == 5


async def test_import_from_yaml_ffmpeg(hass: HomeAssistant, canary) -> None:
    """Test import from YAML with ffmpeg arguments."""
    with patch(
        "homeassistant.components.canary.async_setup_entry",
        return_value=True,
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: YAML_CONFIG,
                CAMERA_DOMAIN: [{"platform": DOMAIN, CONF_FFMPEG_ARGUMENTS: "-v"}],
            },
        )
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert entries[0].data[CONF_USERNAME] == "test-username"
    assert entries[0].data[CONF_PASSWORD] == "test-password"
    assert entries[0].data[CONF_TIMEOUT] == 5
    assert entries[0].data.get(CONF_FFMPEG_ARGUMENTS) == "-v"


async def test_unload_entry(hass: HomeAssistant, canary) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert entry
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_async_setup_raises_entry_not_ready(hass: HomeAssistant, canary) -> None:
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    canary.side_effect = ConnectTimeout()

    entry = await init_integration(hass)
    assert entry
    assert entry.state is ConfigEntryState.SETUP_RETRY
