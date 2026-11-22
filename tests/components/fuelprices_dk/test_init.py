"""Test initialization for Fuelprices.dk."""

from unittest.mock import AsyncMock, MagicMock, call

from freezegun.api import FrozenDateTimeFactory
from pybraendstofpriser import Flist
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
)

from homeassistant.components.fuelprices_dk.const import DOMAIN
from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigSubentry,
    ConfigSubentryData,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import client_error, setup_integration
from .conftest import TEST_API_KEY, TEST_COMPANY, TEST_PRICES, TEST_STATION


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the config entry is set up and unloaded correctly."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_braendstofpriser.get_prices_bulk.reset_mock()
    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_braendstofpriser.get_prices_bulk.assert_not_called()


async def test_reload_on_subentry_added(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the entry reloads and adds entities when a subentry is added."""
    await setup_integration(hass, mock_config_entry)

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) == len(TEST_PRICES)

    mock_braendstofpriser.get_prices_bulk.reset_mock()
    mock_braendstofpriser.get_prices_bulk.return_value = (
        await async_load_json_array_fixture(hass, "bulk_prices.json", DOMAIN)
    )

    new_station = {"id": 4321, "name": "Aarhus N"}
    hass.config_entries.async_add_subentry(
        mock_config_entry,
        ConfigSubentry(
            subentry_type="station",
            title=f"{TEST_COMPANY} - {new_station['name']}",
            unique_id=f"{TEST_COMPANY}_{new_station['id']}",
            data={"company": TEST_COMPANY, "station": new_station},
        ),
    )
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) == len(TEST_PRICES) * 2
    mock_braendstofpriser.get_prices_bulk.assert_awaited_once_with([1234, 4321])


async def test_skips_non_station_subentries(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup skips unsupported subentry types."""
    config_entry = MockConfigEntry(
        domain="fuelprices_dk",
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="other",
                title="Other",
                unique_id="other_1",
                data={"company": TEST_COMPANY, "station": TEST_STATION},
            )
        ],
    )
    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert not er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    mock_braendstofpriser.get_prices_bulk.assert_not_called()


async def test_stations_use_flist(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup completes when the API returns an Flist of stations."""
    mock_braendstofpriser.list_stations.return_value = Flist([TEST_STATION])
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (client_error(401), ConfigEntryState.SETUP_ERROR),
        (client_error(500), ConfigEntryState.SETUP_RETRY),
    ],
    ids=["auth_failed", "cannot_connect"],
)
async def test_setup_error_handling(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup handles API errors during the first refresh."""
    mock_braendstofpriser.get_prices_bulk.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize(
    ("mock_config_entry", "expected_requests", "entity_count"),
    [
        pytest.param(1, [], 0, id="last_station"),
        pytest.param(2, [[4321]], 3, id="one_station_remaining"),
    ],
    indirect=["mock_config_entry"],
)
async def test_remove_station(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    expected_requests: list[list[int]],
    entity_count: int,
) -> None:
    """Test removing a station updates the selection without leaving old polling."""
    data = await async_load_json_array_fixture(hass, "bulk_prices.json", DOMAIN)
    mock_braendstofpriser.get_prices_bulk.return_value = data
    await setup_integration(hass, mock_config_entry)

    mock_braendstofpriser.get_prices_bulk.reset_mock()
    mock_braendstofpriser.get_prices_bulk.return_value = data[1:]
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_remove_subentry(mock_config_entry, subentry.subentry_id)
    await hass.async_block_till_done()

    assert mock_braendstofpriser.get_prices_bulk.await_args_list == [
        call(station_ids) for station_ids in expected_requests
    ]
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == entity_count
    )

    mock_braendstofpriser.get_prices_bulk.reset_mock()
    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_braendstofpriser.get_prices_bulk.await_args_list == [
        call(station_ids) for station_ids in expected_requests
    ]


async def test_api_keys_update_independently(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_braendstofpriser_class: MagicMock,
    mock_other_braendstofpriser: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test separate API keys have their own station selections and updates."""
    data = await async_load_json_array_fixture(hass, "bulk_prices.json", DOMAIN)
    mock_braendstofpriser_class.side_effect = {
        TEST_API_KEY: mock_braendstofpriser,
        "other-api-key": mock_other_braendstofpriser,
    }.__getitem__
    mock_braendstofpriser.get_prices_bulk.return_value = data[:1]
    mock_other_braendstofpriser.get_prices_bulk.return_value = data[1:]
    await setup_integration(hass, mock_config_entry)
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "other-api-key"},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="station",
                title="Uno-X - Aarhus N",
                unique_id="Uno-X_4321",
                data={"company": "Uno-X", "station": data[1]["station"]},
            )
        ],
    )
    await setup_integration(hass, other_entry)

    assert mock_braendstofpriser_class.call_args_list == [
        call(TEST_API_KEY),
        call("other-api-key"),
    ]
    mock_braendstofpriser.get_prices_bulk.assert_awaited_once_with([1234])
    mock_other_braendstofpriser.get_prices_bulk.assert_awaited_once_with([4321])
    assert hass.states.get("sensor.aarhus_c_blyfri95").state == "14.29"
    assert hass.states.get("sensor.aarhus_n_blyfri95").state == "15.29"

    mock_braendstofpriser.get_prices_bulk.reset_mock()
    mock_other_braendstofpriser.get_prices_bulk.reset_mock()
    data[0]["prices"]["Blyfri95"] = "16.29"
    data[1]["prices"]["Blyfri95"] = "17.29"
    freezer.tick(3600)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_braendstofpriser.get_prices_bulk.assert_awaited_once_with([1234])
    mock_other_braendstofpriser.get_prices_bulk.assert_awaited_once_with([4321])
    assert hass.states.get("sensor.aarhus_c_blyfri95").state == "16.29"
    assert hass.states.get("sensor.aarhus_n_blyfri95").state == "17.29"
