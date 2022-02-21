"""Test the GitHub init file."""
from pytest import LogCaptureFixture

from homeassistant.components.github.const import CONF_REPOSITORIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import setup_github_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_device_registry_cleanup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    caplog: LogCaptureFixture,
) -> None:
    """Test that we remove untracked repositories from the decvice registry."""
    mock_config_entry.options = {CONF_REPOSITORIES: ["home-assistant/core"]}
    await setup_github_integration(hass, mock_config_entry, aioclient_mock)

    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(
        registry=device_registry,
        config_entry_id=mock_config_entry.entry_id,
    )

    assert len(devices) == 1

    mock_config_entry.options = {CONF_REPOSITORIES: []}
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        f"Unlinking device {devices[0].id} for untracked repository home-assistant/core from config entry {mock_config_entry.entry_id}"
        in caplog.text
    )

    devices = dr.async_entries_for_config_entry(
        registry=device_registry,
        config_entry_id=mock_config_entry.entry_id,
    )

    assert len(devices) == 0
