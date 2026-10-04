"""Test the HP Printer sensor platform."""

from dataclasses import replace
from unittest.mock import AsyncMock

from aiohpprinter import HpPrinterData, HpPrinterStatus
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hp_printer.coordinator import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

STATUS = "sensor.hp_officejet_pro_9020_series_status"
CYAN_LEVEL = "sensor.hp_officejet_pro_9020_series_cyan_level"
PRINTED_PAGES = "sensor.hp_officejet_pro_9020_series_printed_pages"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hp_printer")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensors_added_when_data_appears(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_data: HpPrinterData,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors are created once the printer first reports their data."""
    mock_hp_printer.update.return_value = HpPrinterData(
        online=True, device=mock_data.device, status=mock_data.status
    )
    await setup_integration(hass, mock_config_entry)

    assert [
        entry.entity_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    ] == [STATUS]

    mock_hp_printer.update.return_value = mock_data
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(CYAN_LEVEL))
    assert state.state == "40.0"
    assert (state := hass.states.get(PRINTED_PAGES))
    assert state.state == "875"


@pytest.mark.parametrize(
    "status",
    [
        pytest.param(HpPrinterStatus(device_status="somethingnew"), id="unknown"),
        pytest.param(HpPrinterStatus(device_status=None), id="missing"),
        pytest.param(None, id="no_status"),
    ],
)
async def test_status_not_reported(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_data: HpPrinterData,
    freezer: FrozenDateTimeFactory,
    status: HpPrinterStatus | None,
) -> None:
    """Test the status is unknown when the printer reports no known status."""
    await setup_integration(hass, mock_config_entry)

    mock_hp_printer.update.return_value = replace(mock_data, status=status)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(STATUS))
    assert state.state == STATE_UNKNOWN


async def test_consumable_removed(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_data: HpPrinterData,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a consumable sensor is unavailable while its cartridge is missing."""
    await setup_integration(hass, mock_config_entry)
    assert (state := hass.states.get(CYAN_LEVEL))
    assert state.state == "40.0"

    mock_hp_printer.update.return_value = replace(
        mock_data,
        consumables=[
            consumable
            for consumable in mock_data.consumables
            if consumable.consumable_id != "C"
        ],
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(CYAN_LEVEL))
    assert state.state == STATE_UNAVAILABLE

    mock_hp_printer.update.return_value = mock_data
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(CYAN_LEVEL))
    assert state.state == "40.0"
