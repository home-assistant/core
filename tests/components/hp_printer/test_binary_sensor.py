"""Test the HP Printer binary sensor platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiohpprinter import HpPrinterData
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hp_printer.coordinator import UPDATE_INTERVAL
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

WIFI = "binary_sensor.hp_officejet_pro_9020_series_wi_fi"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Only set up the binary sensor platform."""
    with patch(
        "homeassistant.components.hp_printer.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        yield


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


async def test_binary_sensors_added_when_data_appears(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_data: HpPrinterData,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensors are created once the printer first reports their data."""
    mock_hp_printer.update.return_value = HpPrinterData(
        online=True, device=mock_data.device, status=mock_data.status
    )
    await setup_integration(hass, mock_config_entry)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    mock_hp_printer.update.return_value = mock_data
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(WIFI))
    assert state.state == STATE_ON
