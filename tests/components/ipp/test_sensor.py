"""Tests for the IPP sensor platform."""

from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyipp import Counters, Printer
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ipp.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.freeze_time("2019-11-11 09:10:32+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
) -> None:
    """Test the creation and values of the IPP sensors."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_disabled_by_default_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the disabled by default IPP sensors."""
    entity_id = entity_registry.async_get_entity_id(
        "sensor", "ipp", f"{init_integration.unique_id}_uptime"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is None

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_missing_entry_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_ipp: AsyncMock,
) -> None:
    """Test the unique_id of IPP sensor when printer is missing identifiers."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id=None)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity = entity_registry.async_get("sensor.test_ha_1000_series")
    assert entity
    assert entity.unique_id == f"{mock_config_entry.entry_id}_printer"


async def test_no_page_count_sensors_when_unsupported(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_printer: Printer,
    mock_ipp: MagicMock,
) -> None:
    """Test that page count sensors are not created when printer doesn't support them."""
    mock_printer.counters = Counters(
        impressions_completed=None,
        impressions_completed_col={},
        pages_completed=None,
        media_sheets_completed=None,
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    unique_id = mock_config_entry.unique_id
    for key in (
        "pages_completed",
        "impressions_completed",
        "media_sheets_completed",
        "impressions_completed_monochrome",
        "impressions_completed_full_color",
    ):
        assert not entity_registry.async_get_entity_id(
            "sensor", "ipp", f"{unique_id}_{key}"
        )


async def test_page_count_sensors_with_partial_counters(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_printer: Printer,
    mock_ipp: MagicMock,
) -> None:
    """Test only the counters the printer reports get sensors."""
    mock_printer.counters = Counters(
        impressions_completed=2468,
        impressions_completed_col={"monochrome": 1500},
        pages_completed=None,
        media_sheets_completed=None,
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unique_id = mock_config_entry.unique_id
    for key in (
        "pages_completed",
        "media_sheets_completed",
        "impressions_completed_full_color",
    ):
        assert not entity_registry.async_get_entity_id(
            "sensor", "ipp", f"{unique_id}_{key}"
        )

    state = hass.states.get("sensor.test_ha_1000_series_impressions_completed")
    assert state
    assert state.state == "2468"

    state = hass.states.get(
        "sensor.test_ha_1000_series_monochrome_impressions_completed"
    )
    assert state
    assert state.state == "1500"


async def test_page_count_unknown_when_counter_missing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_printer: Printer,
) -> None:
    """Test a page count sensor becomes unknown when the printer stops reporting it."""
    assert hass.states.get("sensor.test_ha_1000_series_pages_completed").state == "1234"

    mock_printer.counters.pages_completed = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.test_ha_1000_series_pages_completed").state
        == STATE_UNKNOWN
    )
