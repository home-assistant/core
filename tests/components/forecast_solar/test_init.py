"""Tests for the Forecast.Solar integration."""

from unittest.mock import MagicMock, patch

from forecast_solar import ForecastSolarConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.forecast_solar.const import (
    CONF_AZIMUTH,
    CONF_DAMPING,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_DECLINATION,
    CONF_INVERTER_SIZE,
    CONF_MODULES_POWER,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test the Forecast.Solar configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await async_setup_component(hass, "forecast_solar", {})

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)


@patch(
    "homeassistant.components.forecast_solar.coordinator.ForecastSolar.estimate",
    side_effect=ForecastSolarConnectionError,
)
async def test_config_entry_not_ready(
    mock_request: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Forecast.Solar configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_request.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_migration_v1_to_v3(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test config entry migration from v1 to v3.

    v1 entries have:
    - "modules power" (space) as the wattage key
    - A single CONF_DAMPING value (not split into morning/evening)
    - No lat/lon in options if using home location (stored as flag in data)

    After migration to v3:
    - CONF_MODULES_POWER replaces "modules power"
    - CONF_DAMPING_MORNING and CONF_DAMPING_EVENING replace CONF_DAMPING
    - CONF_LATITUDE and CONF_LONGITUDE are always present in options
    """
    mock_config_entry = MockConfigEntry(
        title="Green House",
        unique_id="unique_v1",
        domain=DOMAIN,
        version=1,
        data={},
        options={
            CONF_API_KEY: "abcdef12345",
            CONF_LATITUDE: 52.42,
            CONF_LONGITUDE: 4.42,
            CONF_DECLINATION: 30,
            CONF_AZIMUTH: 190,
            "modules power": 5100,
            CONF_DAMPING: 0.5,
            CONF_INVERTER_SIZE: 2000,
        },
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    migrated = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert migrated == snapshot

    # Explicit assertions so failures are readable without snapshot diffs
    assert migrated.version == 3
    assert CONF_MODULES_POWER in migrated.options
    assert migrated.options[CONF_MODULES_POWER] == 5100
    assert "modules power" not in migrated.options
    assert migrated.options[CONF_DAMPING_MORNING] == 0.5
    assert migrated.options[CONF_DAMPING_EVENING] == 0.5
    assert CONF_DAMPING not in migrated.options


async def test_migration_v2_to_v3_with_manual_location(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test v2 -> v3 migration for entries that already had manual lat/lon in options.

    These entries should pass through migration unchanged (lat/lon already present).
    """
    mock_config_entry = MockConfigEntry(
        title="Garage East",
        unique_id="unique_v2_manual",
        domain=DOMAIN,
        version=2,
        data={},
        options={
            CONF_API_KEY: "abcdef12345",
            CONF_LATITUDE: 52.42,
            CONF_LONGITUDE: 4.42,
            CONF_DECLINATION: 30,
            CONF_AZIMUTH: 190,
            CONF_MODULES_POWER: 5100,
            CONF_DAMPING_MORNING: 0.5,
            CONF_DAMPING_EVENING: 0.5,
            CONF_INVERTER_SIZE: 2000,
        },
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    migrated = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert migrated == snapshot

    assert migrated.version == 3
    # Existing coordinates must be preserved, not overwritten with hass.config values
    assert migrated.options[CONF_LATITUDE] == 52.42
    assert migrated.options[CONF_LONGITUDE] == 4.42


async def test_migration_v2_to_v3_home_location_backfilled(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test v2 -> v3 migration for entries using home location (no lat/lon in options).

    These entries had no lat/lon in options — the coordinator used to read them
    from hass.config at runtime. Migration must backfill them from hass.config.
    """
    hass.config.latitude = 48.85
    hass.config.longitude = 2.35

    mock_config_entry = MockConfigEntry(
        title="Roof South",
        unique_id="unique_v2_home",
        domain=DOMAIN,
        version=2,
        data={},
        options={
            CONF_DECLINATION: 30,
            CONF_AZIMUTH: 180,
            CONF_MODULES_POWER: 4000,
            CONF_DAMPING_MORNING: 0.0,
            CONF_DAMPING_EVENING: 0.0,
        },
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    migrated = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert migrated == snapshot

    assert migrated.version == 3
    # Coordinates must have been backfilled from hass.config
    assert migrated.options[CONF_LATITUDE] == 48.85
    assert migrated.options[CONF_LONGITUDE] == 2.35
