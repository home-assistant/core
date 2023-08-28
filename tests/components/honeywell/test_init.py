"""Test honeywell setup process."""
from unittest.mock import MagicMock, create_autospec, patch

import aiosomecomfort
import pytest

from homeassistant.components.honeywell.const import (
    CONF_COOL_AWAY_TEMPERATURE,
    CONF_HEAT_AWAY_TEMPERATURE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import MockConfigEntry

MIGRATE_OPTIONS_KEYS = {CONF_COOL_AWAY_TEMPERATURE, CONF_HEAT_AWAY_TEMPERATURE}


@patch("homeassistant.components.honeywell.UPDATE_LOOP_SLEEP_TIME", 0)
async def test_setup_entry(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Initialize the config entry."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.async_entity_ids_count() == 3
    )  # 1 climate entity; 2 sensor entities


async def test_setup_multiple_thermostats(
    hass: HomeAssistant, config_entry: MockConfigEntry, location, another_device
) -> None:
    """Test that the config form is shown."""
    location.devices_by_id[another_device.deviceid] = another_device
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.async_entity_ids_count() == 6
    )  # 2 climate entities; 4 sensor entities


async def test_setup_multiple_thermostats_with_same_deviceid(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_entry: MockConfigEntry,
    device,
    client,
) -> None:
    """Test Honeywell TCC API returning duplicate device IDs."""
    mock_location2 = create_autospec(aiosomecomfort.Location, instance=True)
    mock_location2.locationid.return_value = "location2"
    mock_location2.devices_by_id = {device.deviceid: device}
    client.locations_by_id["location2"] = mock_location2
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.async_entity_ids_count() == 3
    )  # 1 climate entity; 2 sensor entities
    assert "Platform honeywell does not generate unique IDs" not in caplog.text


async def test_away_temps_migration(hass: HomeAssistant) -> None:
    """Test away temps migrate to config options."""
    legacy_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "fake",
            CONF_PASSWORD: "user",
            CONF_COOL_AWAY_TEMPERATURE: 1,
            CONF_HEAT_AWAY_TEMPERATURE: 2,
        },
        options={},
    )

    legacy_config.add_to_hass(hass)
    await hass.config_entries.async_setup(legacy_config.entry_id)
    await hass.async_block_till_done()
    assert legacy_config.options == {
        CONF_COOL_AWAY_TEMPERATURE: 1,
        CONF_HEAT_AWAY_TEMPERATURE: 2,
    }


async def test_login_error(
    hass: HomeAssistant, client: MagicMock, config_entry: MagicMock
) -> None:
    """Test login errors from API."""
    client.login.side_effect = aiosomecomfort.AuthError
    await init_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_connection_error(
    hass: HomeAssistant, client: MagicMock, config_entry: MagicMock
) -> None:
    """Test Connection errors from API."""
    client.login.side_effect = aiosomecomfort.ConnectionError
    await init_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_no_devices(
    hass: HomeAssistant, client: MagicMock, config_entry: MagicMock
) -> None:
    """Test no devices from API."""
    client.locations_by_id = {}
    await init_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
