"""Tests for the Probe Plus init."""

from unittest.mock import patch

import pytest

from homeassistant.components.probe_plus.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_probe_plus")
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the config entry."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bluetooth.async_scanner_count",
            return_value=1,
        ),
        patch("homeassistant.components.bluetooth.async_get_scanner"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("legacy_unique_id", "expected_unique_id"),
    [
        pytest.param(
            "aa:bb:cc:dd:ee:ff_probe_temperature",
            "aa:bb:cc:dd:ee:ff_probe_temperature_0",
            id="probe_temperature",
        ),
        pytest.param(
            "aa:bb:cc:dd:ee:ff_probe_battery",
            "aa:bb:cc:dd:ee:ff_probe_battery_0",
            id="probe_battery",
        ),
        pytest.param(
            "aa:bb:cc:dd:ee:ff_probe_voltage",
            "aa:bb:cc:dd:ee:ff_probe_voltage_0",
            id="probe_voltage",
        ),
        pytest.param(
            "aa:bb:cc:dd:ee:ff_probe_rssi",
            "aa:bb:cc:dd:ee:ff_probe_rssi_0",
            id="probe_rssi",
        ),
        pytest.param(
            "aa:bb:cc:dd:ee:ff_relay_battery",
            "aa:bb:cc:dd:ee:ff_relay_battery",
            id="relay_battery_unchanged",
        ),
        pytest.param(
            "unrelated_unique_id",
            "unrelated_unique_id",
            id="unrelated_unchanged",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_migrate_entity_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    legacy_unique_id: str,
    expected_unique_id: str,
) -> None:
    """Test migrating entity unique IDs."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=0,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    entity = entity_registry.async_get_or_create(
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=legacy_unique_id,
        config_entry=entry,
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 1
    assert entry.minor_version == 1

    migrated_entity = entity_registry.async_get(entity.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.unique_id == expected_unique_id


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migrate_entry_no_unique_id(
    hass: HomeAssistant,
) -> None:
    """Test migration when unique_id is None."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=0,
        unique_id=None,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 1
    assert entry.minor_version == 0


async def test_migrate_entry_future_version(
    hass: HomeAssistant,
) -> None:
    """Test migration fails for future major version."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=0,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
