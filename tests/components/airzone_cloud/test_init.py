"""Define tests for the Airzone Cloud init."""

from unittest.mock import patch

from homeassistant.components.airzone_cloud.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .util import CONFIG

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload."""

    config_entry = MockConfigEntry(
        data=CONFIG,
        domain=DOMAIN,
        unique_id="airzone_cloud_unique_id",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.login",
        return_value=None,
    ), patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.list_installations",
        return_value=[],
    ), patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.update_installation",
        return_value=None,
    ), patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.update",
        return_value=None,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED
