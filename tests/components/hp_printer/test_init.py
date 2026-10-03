"""Test the HP Printer integration setup."""

from unittest.mock import AsyncMock

from aiohpprinter import HpPrinterData
from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hp_printer.const import DOMAIN
from homeassistant.components.hp_printer.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import SERIAL_NUMBER

from tests.common import MockConfigEntry, async_fire_time_changed

STATUS = "sensor.hp_officejet_pro_9020_series_status"


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a config entry loads and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_device_info(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the printer is registered as a device."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL_NUMBER), mock_config_entry.entry_id
    )
    assert device == snapshot


async def test_setup_offline_is_retried(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an offline printer triggers a setup retry."""
    mock_hp_printer.update.return_value = HpPrinterData(online=False)
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_offline_marks_entities_unavailable(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_data: HpPrinterData,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities go unavailable while the printer is offline and recover."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(STATUS).state == "in_power_save"

    mock_hp_printer.update.return_value = HpPrinterData(online=False)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(STATUS).state == STATE_UNAVAILABLE

    mock_hp_printer.update.return_value = mock_data
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(STATUS).state == "in_power_save"
