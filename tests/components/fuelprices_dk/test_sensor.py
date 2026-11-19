"""Test sensor platform for Fuelprices.dk."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fuelprices_dk.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import client_error, setup_integration


async def test_sensors(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor entities."""
    with patch("homeassistant.components.fuelprices_dk.PLATFORMS", ["sensor"]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_updates(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensor updates when the coordinator refreshes."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.aarhus_c_blyfri95").state == "14.29"

    mock_braendstofpriser.get_prices_bulk.return_value[0]["prices"]["Blyfri95"] = (
        "15.99"
    )

    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.aarhus_c_blyfri95").state == "15.99"


async def test_sensor_becomes_unavailable_when_product_missing(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sensor becomes unavailable when its product is not returned."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.aarhus_c_blyfri95").state == "14.29"

    del mock_braendstofpriser.get_prices_bulk.return_value[0]["prices"]["Blyfri95"]

    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.aarhus_c_blyfri95").state == STATE_UNAVAILABLE


async def test_sensor_ignores_non_numeric_price(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sensor reports unknown when the API returns a non-numeric price."""
    await setup_integration(hass, mock_config_entry)

    mock_braendstofpriser.get_prices_bulk.return_value[0]["prices"]["Blyfri95"] = "n/a"

    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.aarhus_c_blyfri95").state == STATE_UNKNOWN


@pytest.mark.parametrize("mock_config_entry", [2], indirect=True)
async def test_bulk_updates(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test all stations share one update and retain their entity identities."""
    data = await async_load_json_array_fixture(hass, "bulk_prices.json", DOMAIN)
    mock_braendstofpriser.get_prices_bulk.return_value = data
    await setup_integration(hass, mock_config_entry)

    mock_braendstofpriser.get_prices_bulk.assert_awaited_once_with([1234, 4321])
    mock_braendstofpriser.get_prices.assert_not_called()
    assert hass.states.get("sensor.aarhus_c_blyfri95").state == "14.29"
    assert hass.states.get("sensor.aarhus_n_blyfri95").state == "15.29"
    first, second = mock_config_entry.subentries.values()
    entity = entity_registry.async_get("sensor.aarhus_c_blyfri95")
    assert entity.unique_id == "1234_price_blyfri95"
    assert entity.config_subentry_id == first.subentry_id
    entity = entity_registry.async_get("sensor.aarhus_n_blyfri95")
    assert entity.unique_id == "4321_price_blyfri95"
    assert entity.config_subentry_id == second.subentry_id

    mock_braendstofpriser.get_prices_bulk.reset_mock()
    data[0]["prices"]["Blyfri95"] = "16.29"
    data[1]["prices"]["Blyfri95"] = "17.29"
    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_braendstofpriser.get_prices_bulk.assert_awaited_once_with([1234, 4321])
    assert hass.states.get("sensor.aarhus_c_blyfri95").state == "16.29"
    assert hass.states.get("sensor.aarhus_n_blyfri95").state == "17.29"


@pytest.mark.parametrize("mock_config_entry", [2], indirect=True)
async def test_missing_station_recovers(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an omitted station does not affect other stations and can recover."""
    data = await async_load_json_array_fixture(hass, "bulk_prices.json", DOMAIN)
    mock_braendstofpriser.get_prices_bulk.return_value = data
    await setup_integration(hass, mock_config_entry)

    data[1]["prices"]["Blyfri95"] = "16.29"
    mock_braendstofpriser.get_prices_bulk.return_value = data[1:]
    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.aarhus_c_blyfri95").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.aarhus_n_blyfri95").state == "16.29"

    mock_braendstofpriser.get_prices_bulk.return_value = data
    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.aarhus_c_blyfri95").state == "14.29"
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == 6
    )


@pytest.mark.parametrize("mock_config_entry", [2], indirect=True)
async def test_station_missing_at_setup(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors are added when a station first appears in an update."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.aarhus_n_blyfri95") is None

    mock_braendstofpriser.get_prices_bulk.return_value = (
        await async_load_json_array_fixture(hass, "bulk_prices.json", DOMAIN)
    )
    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.aarhus_n_blyfri95").state == "15.29"


@pytest.mark.parametrize("mock_config_entry", [2], indirect=True)
@pytest.mark.parametrize("status", [500, 429])
async def test_failed_update_recovers(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    status: int,
) -> None:
    """Test a failed bulk request marks all stations unavailable until recovery."""
    mock_braendstofpriser.get_prices_bulk.return_value = (
        await async_load_json_array_fixture(hass, "bulk_prices.json", DOMAIN)
    )
    await setup_integration(hass, mock_config_entry)

    mock_braendstofpriser.get_prices_bulk.side_effect = client_error(status)
    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.aarhus_c_blyfri95").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.aarhus_n_blyfri95").state == STATE_UNAVAILABLE

    mock_braendstofpriser.get_prices_bulk.side_effect = None
    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.aarhus_c_blyfri95").state == "14.29"
    assert hass.states.get("sensor.aarhus_n_blyfri95").state == "15.29"


@pytest.mark.parametrize("mock_config_entry", [2], indirect=True)
async def test_invalid_api_key_starts_reauth(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an invalid key starts one reauth flow and stops polling."""
    mock_braendstofpriser.get_prices_bulk.return_value = (
        await async_load_json_array_fixture(hass, "bulk_prices.json", DOMAIN)
    )
    await setup_integration(hass, mock_config_entry)

    mock_braendstofpriser.get_prices_bulk.side_effect = client_error(401)
    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
    assert hass.states.get("sensor.aarhus_c_blyfri95").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.aarhus_n_blyfri95").state == STATE_UNAVAILABLE

    mock_braendstofpriser.get_prices_bulk.reset_mock()
    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_braendstofpriser.get_prices_bulk.assert_not_called()
