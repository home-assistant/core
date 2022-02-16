"""Tests for the MJPEG IP Camera integration."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.mjpeg.const import (
    CONF_MJPEG_URL,
    CONF_STILL_IMAGE_URL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mjpeg_requests: MagicMock,
) -> None:
    """Test the MJPEG IP Camera configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_reload_config_entry(
    hass: HomeAssistant,
    mock_reload_entry: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the MJPEG IP Camera configuration entry is reloaded on change."""
    assert len(mock_reload_entry.mock_calls) == 0
    hass.config_entries.async_update_entry(
        init_integration, options={"something": "else"}
    )
    assert len(mock_reload_entry.mock_calls) == 1


async def test_import_config(
    hass: HomeAssistant,
    mock_mjpeg_requests: MagicMock,
    mock_setup_entry: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test MJPEG IP Camera being set up from config via import."""
    assert await async_setup_component(
        hass,
        CAMERA_DOMAIN,
        {
            CAMERA_DOMAIN: {
                "platform": DOMAIN,
                CONF_MJPEG_URL: "http://example.com/mjpeg",
                CONF_NAME: "Random Camera",
                CONF_PASSWORD: "supersecret",
                CONF_STILL_IMAGE_URL: "http://example.com/still",
                CONF_USERNAME: "frenck",
                CONF_VERIFY_SSL: False,
            }
        },
    )
    await hass.async_block_till_done()

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1

    assert "the MJPEG IP Camera platform in YAML is deprecated" in caplog.text

    entry = config_entries[0]
    assert entry.title == "Random Camera"
    assert entry.unique_id is None
    assert entry.data == {}
    assert entry.options == {
        CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
        CONF_MJPEG_URL: "http://example.com/mjpeg",
        CONF_PASSWORD: "supersecret",
        CONF_STILL_IMAGE_URL: "http://example.com/still",
        CONF_USERNAME: "frenck",
        CONF_VERIFY_SSL: False,
    }
