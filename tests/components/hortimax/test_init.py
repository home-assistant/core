"""Test setting up and tearing down the Ridder HortiMaX Pro integration."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from aiohortos import (
    Device,
    HortosAuthenticationError,
    HortosConnectionError,
    Readout,
    Source,
)
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


async def test_no_controllers_still_loads(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
) -> None:
    """Test an entry whose controllers have gone loads empty instead of retrying.

    A reachable API means setup succeeded, so failing it would retry a working
    connection forever.
    """
    mock_hortos_client.get_devices.return_value = []

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.states.async_entity_ids("sensor")


async def test_new_controller_is_added(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a controller that only shows up later is registered with its sources.

    Sources resolve their controller from the registry when their first entity
    is added, so the controller has to be there by then.
    """
    second_device = "HOR00000000.001"
    await setup_integration(hass, mock_config_entry)
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, second_device), mock_config_entry.entry_id
        )
        is None
    )

    mock_hortos_client.get_devices.return_value = [
        Device(name=DEVICE, label=DEVICE_LABEL, public_id="public-id"),
        Device(name=second_device, label="Greenhouse Cabrio", public_id="public-id-2"),
    ]
    mock_hortos_client.get_latest_readouts.side_effect = lambda device_name: (
        load_readouts()
        if device_name == DEVICE
        else [
            Readout(
                identifier="OutsideTemperature-Measured",
                name="Outside temperature",
                unit="DegreeCelsius",
                source=Source(
                    name="Weather station 001",
                    type="WeatherStation",
                    user_defined_name="Weerstation Cabrio",
                ),
                value=21.5,
            )
        ]
    )

    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    controller = device_registry.async_get_device_by_identifier(
        (DOMAIN, second_device), mock_config_entry.entry_id
    )
    assert controller is not None
    assert controller.name == "Greenhouse Cabrio"

    source = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{second_device}::WeatherStation::Weather station 001"),
        mock_config_entry.entry_id,
    )
    assert source is not None
    assert source.via_device_id == controller.id

    state = hass.states.get("sensor.weerstation_cabrio_outside_temperature")
    assert state is not None
    assert state.state == "21.5"


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


async def test_failed_poll_registers_no_controller(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a poll that fails part way through registers no controller.

    Controllers are discovered before their readouts are read, so registering
    them early would leave devices behind for an update that is rejected.
    """
    mock_hortos_client.get_latest_readouts.side_effect = HortosConnectionError("boom")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, DEVICE), mock_config_entry.entry_id
        )
        is None
    )


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
