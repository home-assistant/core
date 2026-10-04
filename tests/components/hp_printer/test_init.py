"""Test the HP Printer integration setup."""

from collections.abc import Callable
from dataclasses import replace
from unittest.mock import AsyncMock

from aiohpprinter import HpPrinterData
from freezegun.api import FrozenDateTimeFactory
import pytest
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

UNUSABLE_DATA = [
    pytest.param(lambda data: HpPrinterData(online=False), id="offline"),
    pytest.param(
        # The host now points to another printer, e.g. after a DHCP change.
        lambda data: replace(
            data, device=replace(data.device, serial_number="OTHER_SERIAL")
        ),
        id="other_printer",
    ),
]


@pytest.mark.usefixtures("mock_hp_printer")
async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a config entry loads and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_hp_printer")
async def test_device_info(
    hass: HomeAssistant,
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


@pytest.mark.parametrize("unusable_data", UNUSABLE_DATA)
async def test_setup_is_retried(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_data: HpPrinterData,
    unusable_data: Callable[[HpPrinterData], HpPrinterData],
) -> None:
    """Test setup is retried when the printer data cannot be used."""
    mock_hp_printer.update.return_value = unusable_data(mock_data)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("unusable_data", UNUSABLE_DATA)
async def test_entities_unavailable(
    hass: HomeAssistant,
    mock_hp_printer: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_data: HpPrinterData,
    freezer: FrozenDateTimeFactory,
    unusable_data: Callable[[HpPrinterData], HpPrinterData],
) -> None:
    """Test entities go unavailable while the printer data cannot be used."""
    await setup_integration(hass, mock_config_entry)
    assert (state := hass.states.get(STATUS))
    assert state.state == "in_power_save"

    mock_hp_printer.update.return_value = unusable_data(mock_data)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(STATUS))
    assert state.state == STATE_UNAVAILABLE

    mock_hp_printer.update.return_value = mock_data
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(STATUS))
    assert state.state == "in_power_save"
