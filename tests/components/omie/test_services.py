"""Test the OMIE - Spain and Portugal electricity prices services."""

import datetime as dt
from unittest.mock import MagicMock

import aiohttp
from pyomie.model import OMIEResults
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.omie.const import DOMAIN
from homeassistant.components.omie.services import (
    ATTR_COUNTRIES,
    SERVICE_GET_PRICES_FOR_DATE,
)
from homeassistant.const import ATTR_DATE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration, spot_price_fetcher

from tests.common import MockConfigEntry

TEST_DATE = "2025-10-15"
TEST_DST_DATE = "2025-10-26"


@pytest.mark.parametrize(
    "countries",
    [
        pytest.param(["es"], id="spain"),
        pytest.param(["pt"], id="portugal"),
        pytest.param(["es", "pt"], id="both"),
    ],
)
async def test_get_prices_for_date(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyomie: MagicMock,
    mock_omie_results_jan15: OMIEResults,
    countries: list[str],
    snapshot: SnapshotAssertion,
) -> None:
    """Test the get_prices_for_date service response."""
    await setup_integration(hass, mock_config_entry)
    mock_pyomie.spot_price.side_effect = spot_price_fetcher(
        {TEST_DATE: mock_omie_results_jan15}
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PRICES_FOR_DATE,
        {ATTR_DATE: TEST_DATE, ATTR_COUNTRIES: countries},
        blocking=True,
        return_response=True,
    )

    assert response == snapshot


async def test_get_prices_for_date_default_country(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyomie: MagicMock,
    mock_omie_results_jan15: OMIEResults,
) -> None:
    """Test the get_prices_for_date service returns both countries by default."""
    await setup_integration(hass, mock_config_entry)
    mock_pyomie.spot_price.side_effect = spot_price_fetcher(
        {TEST_DATE: mock_omie_results_jan15}
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PRICES_FOR_DATE,
        {ATTR_DATE: TEST_DATE},
        blocking=True,
        return_response=True,
    )

    assert set(response) == {"es", "pt"}


async def test_get_prices_for_date_dst_fall_back(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyomie: MagicMock,
    mock_omie_results_oct26_dst: OMIEResults,
) -> None:
    """Test interval ends on the 25-hour DST fall-back day."""
    await setup_integration(hass, mock_config_entry)
    mock_pyomie.spot_price.side_effect = spot_price_fetcher(
        {TEST_DST_DATE: mock_omie_results_oct26_dst}
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PRICES_FOR_DATE,
        {ATTR_DATE: TEST_DST_DATE, ATTR_COUNTRIES: ["es"]},
        blocking=True,
        return_response=True,
    )

    intervals = response["es"]
    assert len(intervals) == 100
    for interval in intervals:
        start = dt.datetime.fromisoformat(interval["start"])
        end = dt.datetime.fromisoformat(interval["end"])
        assert end - start == dt.timedelta(minutes=15)

    last_cest_quarter = next(
        interval
        for interval in intervals
        if interval["start"] == "2025-10-26T02:45:00+02:00"
    )
    assert last_cest_quarter["end"] == "2025-10-26T02:00:00+01:00"


@pytest.mark.parametrize(
    ("side_effect", "expected_exception", "expected_translation_key"),
    [
        pytest.param(
            aiohttp.ClientResponseError(
                request_info=MagicMock(), history=(), status=404
            ),
            ServiceValidationError,
            "data_not_available",
            id="not_published_yet",
        ),
        pytest.param(
            aiohttp.ClientResponseError(
                request_info=MagicMock(), history=(), status=500
            ),
            HomeAssistantError,
            "cannot_connect",
            id="server_error",
        ),
        pytest.param(
            aiohttp.ClientError("Connection error"),
            HomeAssistantError,
            "cannot_connect",
            id="client_error",
        ),
        pytest.param(
            TimeoutError(),
            HomeAssistantError,
            "cannot_connect",
            id="timeout",
        ),
    ],
)
async def test_get_prices_for_date_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyomie: MagicMock,
    side_effect: Exception,
    expected_exception: type[HomeAssistantError],
    expected_translation_key: str,
) -> None:
    """Test the get_prices_for_date service error handling."""
    await setup_integration(hass, mock_config_entry)
    mock_pyomie.spot_price.side_effect = side_effect

    with pytest.raises(expected_exception) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRICES_FOR_DATE,
            {ATTR_DATE: TEST_DATE},
            blocking=True,
            return_response=True,
        )

    assert err.value.translation_key == expected_translation_key


@pytest.mark.usefixtures("mock_pyomie")
async def test_get_prices_for_date_before_market_start(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the get_prices_for_date service with a date before the market start."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRICES_FOR_DATE,
            {ATTR_DATE: "2024-01-15"},
            blocking=True,
            return_response=True,
        )

    assert err.value.translation_key == "date_before_market_start"


@pytest.mark.usefixtures("mock_pyomie")
async def test_get_prices_for_date_unloaded_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the get_prices_for_date service with no loaded config entry."""
    await setup_integration(hass, mock_config_entry)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRICES_FOR_DATE,
            {ATTR_DATE: TEST_DATE},
            blocking=True,
            return_response=True,
        )

    assert err.value.translation_key == "entry_not_loaded"
