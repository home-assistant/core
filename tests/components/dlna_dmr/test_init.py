"""Tests for the DLNA DMR __init__ module."""

from unittest.mock import Mock

from async_upnp_client import UpnpError

from homeassistant.components.dlna_dmr.const import (
    CONF_LISTEN_PORT,
    DOMAIN as DLNA_DOMAIN,
)
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import CONF_NAME, CONF_PLATFORM, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .conftest import MOCK_DEVICE_LOCATION


async def test_import_flow_started(hass: HomeAssistant, domain_data_mock: Mock) -> None:
    """Test import flow of YAML config is started if there's config data."""
    mock_config: ConfigType = {
        MEDIA_PLAYER_DOMAIN: [
            {
                CONF_PLATFORM: DLNA_DOMAIN,
                CONF_URL: MOCK_DEVICE_LOCATION,
                CONF_LISTEN_PORT: 1234,
            },
            {
                CONF_PLATFORM: "other_domain",
                CONF_URL: MOCK_DEVICE_LOCATION,
                CONF_NAME: "another device",
            },
        ]
    }

    # Device is not available yet
    domain_data_mock.upnp_factory.async_create_device.side_effect = UpnpError

    # Run the setup
    await async_setup_component(hass, DLNA_DOMAIN, mock_config)
    await hass.async_block_till_done()

    # Check config_flow has completed
    assert hass.config_entries.flow.async_progress(include_uninitialized=True) == []

    # Check device contact attempt was made
    domain_data_mock.upnp_factory.async_create_device.assert_awaited_once_with(
        MOCK_DEVICE_LOCATION
    )

    # Check the device is added to the unmigrated configs
    assert domain_data_mock.unmigrated_config == {
        MOCK_DEVICE_LOCATION: {
            CONF_PLATFORM: DLNA_DOMAIN,
            CONF_URL: MOCK_DEVICE_LOCATION,
            CONF_LISTEN_PORT: 1234,
        }
    }
