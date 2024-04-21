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
from homeassistant.helpers import device_registry as dr

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
        hass.states.async_entity_ids_count() == 4
    )  # 1 climate entity; 2 sensor entities


@patch("homeassistant.components.honeywell.UPDATE_LOOP_SLEEP_TIME", 0)
async def test_setup_multiple_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, config_entry2: MockConfigEntry
) -> None:
    """Initialize the config entry."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    config_entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry2.entry_id)
    await hass.async_block_till_done()
    assert config_entry2.state is ConfigEntryState.LOADED


async def test_setup_multiple_thermostats(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    location: MagicMock,
    another_device: MagicMock,
) -> None:
    """Test that the config form is shown."""
    location.devices_by_id[another_device.deviceid] = another_device
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.async_entity_ids_count() == 8
    )  # 2 climate entities; 4 sensor entities; 2 switch entities


async def test_setup_multiple_thermostats_with_same_deviceid(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_entry: MockConfigEntry,
    device: MagicMock,
    client: MagicMock,
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
        hass.states.async_entity_ids_count() == 4
    )  # 1 climate entity; 2 sensor entities; 1 switch enitiy
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


async def test_remove_stale_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    location: MagicMock,
    another_device: MagicMock,
    client: MagicMock,
) -> None:
    """Test that the stale device is removed."""
    location.devices_by_id[another_device.deviceid] = another_device

    config_entry_other = MockConfigEntry(
        domain="OtherDomain",
        data={},
        unique_id="unique_id",
    )
    config_entry_other.add_to_hass(hass)
    device_entry_other = device_registry.async_get_or_create(
        config_entry_id=config_entry_other.entry_id,
        identifiers={("OtherDomain", 7654321)},
    )

    device_registry.async_update_device(
        device_entry_other.id,
        add_config_entry_id=config_entry.entry_id,
        merge_identifiers={(DOMAIN, 7654321)},
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.async_entity_ids_count() == 8

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    device_entries_other = dr.async_entries_for_config_entry(
        device_registry, config_entry_other.entry_id
    )

    assert len(device_entries) == 2
    assert any((DOMAIN, 1234567) in device.identifiers for device in device_entries)
    assert any((DOMAIN, 7654321) in device.identifiers for device in device_entries)
    assert any(
        ("OtherDomain", 7654321) in device.identifiers for device in device_entries
    )
    assert len(device_entries_other) == 1
    assert any(
        ("OtherDomain", 7654321) in device.identifiers
        for device in device_entries_other
    )
    assert any(
        (DOMAIN, 7654321) in device.identifiers for device in device_entries_other
    )

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    del location.devices_by_id[another_device.deviceid]

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (
        hass.states.async_entity_ids_count() == 4
    )  # 1 climate entities; 2 sensor entities; 1 switch entity

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    assert len(device_entries) == 1
    assert any((DOMAIN, 1234567) in device.identifiers for device in device_entries)
    assert not any((DOMAIN, 7654321) in device.identifiers for device in device_entries)
    assert not any(
        ("OtherDomain", 7654321) in device.identifiers for device in device_entries
    )

    device_entries_other = dr.async_entries_for_config_entry(
        device_registry, config_entry_other.entry_id
    )
    assert len(device_entries_other) == 1
    assert any(
        ("OtherDomain", 7654321) in device.identifiers
        for device in device_entries_other
    )
