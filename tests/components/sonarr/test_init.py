"""Tests for the Sonsrr integration."""

from unittest.mock import MagicMock, patch

from aiopyarr import ArrAuthenticationException, ArrException

from homeassistant.components.sonarr.const import CONF_BASE_PATH, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SOURCE,
    CONF_SSL,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sonarr: MagicMock,
) -> None:
    """Test the configuration entry not ready."""
    mock_sonarr.async_get_system_status.side_effect = ArrException

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sonarr: MagicMock,
) -> None:
    """Test the configuration entry needing to be re-authenticated."""
    mock_sonarr.async_get_system_status.side_effect = ArrAuthenticationException

    with patch.object(hass.config_entries.flow, "async_init") as mock_flow_init:
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    mock_flow_init.assert_called_once_with(
        DOMAIN,
        context={
            CONF_SOURCE: SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
            "unique_id": mock_config_entry.unique_id,
            "title_placeholders": {"name": mock_config_entry.title},
        },
        data=mock_config_entry.data,
    )


async def test_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sonarr: MagicMock,
) -> None:
    """Test the configuration entry unloading."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sonarr.sensor.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DOMAIN]
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.entry_id in hass.data[DOMAIN]

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]


async def test_migrate_config_entry(hass: HomeAssistant) -> None:
    """Test successful migration of entry data."""
    legacy_config = {
        CONF_API_KEY: "MOCK_API_KEY",
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 8989,
        CONF_SSL: False,
        CONF_VERIFY_SSL: False,
        CONF_BASE_PATH: "/base/",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=legacy_config)
    entry.add_to_hass(hass)

    assert entry.data == legacy_config
    assert entry.version == 1
    assert not entry.unique_id

    with patch("homeassistant.components.sonarr.async_setup_entry", return_value=True):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.data == {
        CONF_API_KEY: "MOCK_API_KEY",
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 8989,
        CONF_SSL: False,
        CONF_VERIFY_SSL: False,
        CONF_BASE_PATH: "/base/",
        CONF_URL: "http://1.2.3.4:8989/base",
    }
    assert entry.version == 2
    assert not entry.unique_id
