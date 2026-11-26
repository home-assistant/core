"""Tests for the Spain fuel prices (Geoportal Gasolineras) sensors."""

from dataclasses import replace
from unittest.mock import AsyncMock

from aioprecioscarburantes import FuelType, PreciosCarburantesConnectionError
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.geoportal_gasolineras.const import SCAN_INTERVAL
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

REPSOL_DIESEL = "sensor.repsol_la_roda_de_andalucia_diesel_a"
REPSOL_E5 = "sensor.repsol_la_roda_de_andalucia_gasoline_95_e5"


async def test_sensors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a sensor is created for each fuel each station sells."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_updates(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test dropped fuels, new fuels, missing stations and errors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(REPSOL_DIESEL).state == "1.825"

    # The Repsol stops selling diesel A and starts selling LPG; the Shell closes
    stations = mock_client.get_stations_by_municipality.return_value
    repsol = stations.stations[0]
    prices = {k: v for k, v in repsol.prices.items() if k is not FuelType.DIESEL_A}
    prices[FuelType.LPG] = 0.999
    mock_client.get_stations_by_municipality.return_value = replace(
        stations, stations=[replace(repsol, prices=prices)]
    )
    await _tick(hass, freezer)
    assert hass.states.get(REPSOL_DIESEL).state == STATE_UNAVAILABLE
    assert hass.states.get(REPSOL_E5).state == "1.575"
    lpg = hass.states.get("sensor.repsol_la_roda_de_andalucia_lpg")
    assert lpg.state == "0.999"
    assert lpg.attributes[ATTR_UNIT_OF_MEASUREMENT] == "€/L"
    assert (
        hass.states.get("sensor.shell_la_roda_de_andalucia_diesel_a").state
        == STATE_UNAVAILABLE
    )

    # Nothing can be fetched
    mock_client.get_stations_by_municipality.side_effect = (
        PreciosCarburantesConnectionError
    )
    await _tick(hass, freezer)
    assert hass.states.get(REPSOL_E5).state == STATE_UNAVAILABLE


async def test_price_per_kilogram(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test fuels sold by weight are priced per kilogram."""
    stations = mock_client.get_stations_by_municipality.return_value
    repsol = stations.stations[0]
    mock_client.get_stations_by_municipality.return_value = replace(
        stations,
        stations=[
            replace(
                repsol,
                prices={
                    **repsol.prices,
                    FuelType.COMPRESSED_NATURAL_GAS: 1.249,
                    FuelType.HYDROGEN: 13.5,
                },
            ),
            stations.stations[1],
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    for entity_id, value in (
        ("sensor.repsol_la_roda_de_andalucia_compressed_natural_gas", "1.249"),
        ("sensor.repsol_la_roda_de_andalucia_hydrogen", "13.5"),
    ):
        state = hass.states.get(entity_id)
        assert state.state == value
        assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "€/kg"
