"""Tests for WaterFurnace integration setup."""

from unittest.mock import Mock

import pytest
from waterfurnace.waterfurnace import WFCredentialError

from homeassistant.components.recorder import Recorder
from homeassistant.components.waterfurnace.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_setup_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test setup fails with auth error."""
    mock_waterfurnace_client.login.side_effect = WFCredentialError(
        "Invalid credentials"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_multi_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client_multi_device: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test setup with multiple devices creates multiple coordinators."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices) == 2


async def test_migrate_unique_id(
    hass: HomeAssistant, mock_waterfurnace_client: Mock
) -> None:
    """Test migration from gwid to account_id unique_id."""
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        title="WaterFurnace test_user",
        data={
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
        },
        unique_id="TEST_GWID_12345",
        version=1,
        minor_version=1,
    )
    old_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(old_entry.entry_id)
    await hass.async_block_till_done()

    assert old_entry.state is ConfigEntryState.LOADED
    assert old_entry.unique_id == "test_account_id"
    assert old_entry.minor_version == 2


async def test_migrate_unique_id_auth_failure(
    hass: HomeAssistant, mock_waterfurnace_client: Mock
) -> None:
    """Test migration fails when login fails."""
    mock_waterfurnace_client.login.side_effect = WFCredentialError(
        "Invalid credentials"
    )
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        title="WaterFurnace test_user",
        data={
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
        },
        unique_id="TEST_GWID_12345",
        version=1,
        minor_version=1,
    )
    old_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(old_entry.entry_id)
    await hass.async_block_till_done()

    assert old_entry.state is ConfigEntryState.MIGRATION_ERROR
    assert old_entry.unique_id == "TEST_GWID_12345"


@pytest.mark.usefixtures("init_integration")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading a config entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("init_integration")
async def test_reload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test reloading a config entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_waterfurnace_client.login.call_count == 3

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_waterfurnace_client.login.call_count == 6


async def test_setup_creates_energy_coordinator(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client: Mock,
) -> None:
    """Test that setup creates both realtime and energy coordinators."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_waterfurnace_client.login.call_count == 3
    assert mock_waterfurnace_client.read_with_retry.call_count == 1
    assert mock_waterfurnace_client.get_energy_data.call_count == 1


async def test_setup_multi_device_energy_coordinators(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client_multi_device: Mock,
) -> None:
    """Test multi-device setup creates energy coordinators with correct gwids."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    gwids = set()
    for gwid, device_data in mock_config_entry.runtime_data.items():
        assert device_data.energy is not None
        assert device_data.energy.gwid == gwid
        gwids.add(gwid)

    assert gwids == {"TEST_GWID_12345", "TEST_GWID_67890"}


async def test_setup_energy_statistic_ids_per_device(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_waterfurnace_client_multi_device: Mock,
) -> None:
    """Test that each device gets a unique statistic_id."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    stat_ids = {
        device_data.energy.statistic_id
        for device_data in mock_config_entry.runtime_data.values()
    }
    assert stat_ids == {
        f"{DOMAIN}:test_gwid_12345_energy",
        f"{DOMAIN}:test_gwid_67890_energy",
    }
