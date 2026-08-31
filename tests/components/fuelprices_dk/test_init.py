"""Test initialization for Fuelprices.dk."""

from unittest.mock import AsyncMock, Mock

from aiohttp import ClientResponseError
from pybraendstofpriser import Flist
from pybraendstofpriser.exceptions import ProductNotFoundError
import pytest

from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigSubentry,
    ConfigSubentryData,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import TEST_API_KEY, TEST_COMPANY, TEST_PRICES, TEST_STATION

from tests.common import MockConfigEntry


def _client_error(status: int) -> ClientResponseError:
    """Create an aiohttp client response error with a specific status code."""
    return ClientResponseError(
        request_info=Mock(),
        history=(),
        status=status,
        message="error",
        headers=None,
    )


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the config entry is set up and unloaded correctly."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


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

    mock_braendstofpriser.get_prices.reset_mock()

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
    assert mock_braendstofpriser.get_prices.await_count == 2


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
    mock_braendstofpriser.get_prices.assert_not_called()


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
        (_client_error(401), ConfigEntryState.SETUP_ERROR),
        (_client_error(500), ConfigEntryState.SETUP_ERROR),
        (ProductNotFoundError("missing"), ConfigEntryState.SETUP_ERROR),
    ],
    ids=["auth_failed", "cannot_connect", "product_not_found"],
)
async def test_setup_error_handling(
    hass: HomeAssistant,
    mock_braendstofpriser: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup handles API errors during the first refresh."""
    mock_braendstofpriser.get_prices.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state
