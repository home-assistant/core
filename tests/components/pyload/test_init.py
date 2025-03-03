"""Test pyLoad init."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyloadapi.exceptions import CannotConnect, InvalidAuth, ParserError
import pytest

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_PATH, CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_entry_setup_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyloadapi: MagicMock,
) -> None:
    """Test integration setup and unload."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect"),
    [CannotConnect, ParserError],
)
async def test_config_entry_setup_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyloadapi: MagicMock,
    side_effect: Exception,
) -> None:
    """Test config entry not ready."""
    mock_pyloadapi.login.side_effect = side_effect
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_setup_invalid_auth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyloadapi: MagicMock,
) -> None:
    """Test config entry authentication."""
    mock_pyloadapi.login.side_effect = InvalidAuth
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    assert any(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_coordinator_update_invalid_auth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyloadapi: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator authentication."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_pyloadapi.login.side_effect = InvalidAuth
    mock_pyloadapi.get_status.side_effect = InvalidAuth

    freezer.tick(timedelta(seconds=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert any(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.usefixtures("mock_pyloadapi")
async def test_migration(
    hass: HomeAssistant,
    config_entry_migrate: MockConfigEntry,
) -> None:
    """Test config entry migration."""

    config_entry_migrate.add_to_hass(hass)
    assert config_entry_migrate.data.get(CONF_PATH) is None

    await hass.config_entries.async_setup(config_entry_migrate.entry_id)
    await hass.async_block_till_done()

    assert config_entry_migrate.state is ConfigEntryState.LOADED
    assert config_entry_migrate.version == 1
    assert config_entry_migrate.minor_version == 1
    assert config_entry_migrate.data[CONF_URL] == "https://pyload.local:8000/"
