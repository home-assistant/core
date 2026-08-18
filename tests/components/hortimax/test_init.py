"""Test setting up and tearing down the Ridder HortiMaX Pro integration."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from aiohortos import HortosAuthenticationError, HortosConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.hortimax.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import DEVICE, DEVICE_LABEL, load_readouts

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_hortos_client")
async def test_load_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entry loads and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_connection_error_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
) -> None:
    """Test an unreachable API leaves the entry in a retry state."""
    mock_hortos_client.get_devices.side_effect = HortosConnectionError("boom")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_no_controllers_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
) -> None:
    """Test an entry whose controllers have gone retries instead of loading empty."""
    mock_hortos_client.get_devices.return_value = []

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.states.async_entity_ids("sensor")


async def test_auth_error_sets_error_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
) -> None:
    """Test a rejected API key leaves the entry in an error state."""
    mock_hortos_client.get_devices.side_effect = HortosAuthenticationError("nope")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_readout_auth_error_sets_error_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
) -> None:
    """Test a key rejected while reading values also errors the entry."""
    mock_hortos_client.get_latest_readouts.side_effect = HortosAuthenticationError(
        "nope"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.usefixtures("mock_hortos_client")
async def test_renamed_source_follows(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test renaming a source in HortiMaX Pro renames its device."""
    await setup_integration(hass, mock_config_entry)
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{DEVICE}::WeatherStation::Weather station 001"),
            mock_config_entry.entry_id,
        ).name
        == "Weerstation"
    )

    readouts = load_readouts()
    mock_hortos_client.get_latest_readouts.return_value = [
        replace(readout, source=replace(readout.source, user_defined_name="Weerhuisje"))
        for readout in readouts
        if readout.source.type == "WeatherStation"
    ] + [readout for readout in readouts if readout.source.type != "WeatherStation"]
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{DEVICE}::WeatherStation::Weather station 001"),
            mock_config_entry.entry_id,
        ).name
        == "Weerhuisje"
    )


@pytest.mark.usefixtures("mock_hortos_client")
async def test_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the controller and its sources become linked devices."""
    await setup_integration(hass, mock_config_entry)

    controller = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE), mock_config_entry.entry_id
    )
    assert controller is not None
    assert controller.name == DEVICE_LABEL
    assert controller.manufacturer == "Ridder"
    assert controller.via_device_id is None

    weather_station = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{DEVICE}::WeatherStation::Weather station 001"),
        mock_config_entry.entry_id,
    )
    assert weather_station is not None
    # The user-defined name wins, with its trailing whitespace stripped.
    assert weather_station.name == "Weerstation"
    assert weather_station.model == "WeatherStation"
    assert weather_station.via_device_id == controller.id

    # Two sources share the user-defined name 'OV1 Tropen', so both get their
    # source type appended.
    screen = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{DEVICE}::Screen::Screen 001"), mock_config_entry.entry_id
    )
    ventilation = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{DEVICE}::VentilationGroup::Ventilation group 001"),
        mock_config_entry.entry_id,
    )
    assert screen is not None
    assert ventilation is not None
    assert screen.name == "OV1 Tropen screen"
    assert ventilation.name == "OV1 Tropen ventilation group"
