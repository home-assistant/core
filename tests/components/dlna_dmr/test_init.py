"""Tests for the DLNA DMR __init__ module."""
from unittest.mock import Mock, patch

from homeassistant.components.dlna_dmr.config_flow import DlnaDmrFlowHandler
from homeassistant.components.dlna_dmr.const import DOMAIN as DLNA_DOMAIN
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import CONF_NAME, CONF_PLATFORM, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .conftest import GOOD_DEVICE_LOCATION

from tests.common import MockConfigEntry


async def test_import_flow_started(
    hass: HomeAssistant, mock_ssdp_scanner: Mock
) -> None:
    """Test import flow of YAML config is started if there's config data."""
    mock_import_data = {
        CONF_PLATFORM: DLNA_DOMAIN,
        CONF_URL: GOOD_DEVICE_LOCATION,
    }

    mock_config: ConfigType = {
        MEDIA_PLAYER_DOMAIN: [
            {
                CONF_PLATFORM: DLNA_DOMAIN,
                CONF_URL: GOOD_DEVICE_LOCATION,
            },
            {
                CONF_PLATFORM: "other_domain",
                CONF_URL: GOOD_DEVICE_LOCATION,
                CONF_NAME: "another device",
            },
        ]
    }

    with patch.object(
        DlnaDmrFlowHandler,
        "async_step_import",
        autospec=True,
        # Not actually what should be returned, but enough to keep FlowManager happy
        return_value={"type": "form"},
    ) as mock_async_step_import:
        await async_setup_component(hass, DLNA_DOMAIN, mock_config)
        await hass.async_block_till_done()

    assert mock_async_step_import.call_count == 1
    assert mock_async_step_import.call_args.args[1] == mock_import_data


async def test_setup_entry(
    hass: HomeAssistant, config_entry_mock: MockConfigEntry, mock_ssdp_scanner: Mock
) -> None:
    """Test async_setup_entry eventually calls our entity setup."""
    with patch(
        "homeassistant.components.dlna_dmr.media_player.async_setup_entry",
        autospec=True,
    ) as mock_setup:
        result = await hass.config_entries.async_setup(config_entry_mock.entry_id)
        assert result is True
        await hass.async_block_till_done()
    assert mock_setup.call_count == 1
    assert mock_setup.call_args.args[0:2] == (hass, config_entry_mock)
