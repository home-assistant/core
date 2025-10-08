"""Test services in Nord Pool."""

import json
from unittest.mock import patch

from pynordpool import (
    API,
    NordPoolAuthenticationError,
    NordPoolEmptyResponseError,
    NordPoolError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nordpool.const import DOMAIN
from homeassistant.components.nordpool.services import (
    ATTR_AREAS,
    ATTR_CONFIG_ENTRY,
    ATTR_CURRENCY,
    ATTR_RESOLUTION,
    SERVICE_GET_PRICE_INDICES_FOR_DATE,
    SERVICE_GET_PRICES_FOR_DATE,
)
from homeassistant.const import ATTR_DATE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry, async_load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_SERVICE_DATA = {
    ATTR_CONFIG_ENTRY: "to_replace",
    ATTR_DATE: "2025-10-01",
    ATTR_AREAS: "SE3",
    ATTR_CURRENCY: "EUR",
}
TEST_SERVICE_DATA_USE_DEFAULTS = {
    ATTR_CONFIG_ENTRY: "to_replace",
    ATTR_DATE: "2025-10-01",
}
TEST_SERVICE_INDICES_DATA_60 = {
    ATTR_CONFIG_ENTRY: "to_replace",
    ATTR_DATE: "2025-10-01",
    ATTR_AREAS: "SE3",
    ATTR_CURRENCY: "SEK",
    ATTR_RESOLUTION: 60,
}
TEST_SERVICE_INDICES_DATA_15 = {
    ATTR_CONFIG_ENTRY: "to_replace",
    ATTR_DATE: "2025-10-01",
    ATTR_AREAS: "SE3",
    ATTR_CURRENCY: "SEK",
    ATTR_RESOLUTION: 15,
}


@pytest.mark.freeze_time("2025-10-01T18:00:00+00:00")
async def test_service_call(
    hass: HomeAssistant,
    load_int: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test get_prices_for_date service call."""

    service_data = TEST_SERVICE_DATA.copy()
    service_data[ATTR_CONFIG_ENTRY] = load_int.entry_id
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PRICES_FOR_DATE,
        service_data,
        blocking=True,
        return_response=True,
    )

    assert response == snapshot
    price_value = response["SE3"][0]["price"]

    service_data = TEST_SERVICE_DATA_USE_DEFAULTS.copy()
    service_data[ATTR_CONFIG_ENTRY] = load_int.entry_id
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PRICES_FOR_DATE,
        service_data,
        blocking=True,
        return_response=True,
    )

    assert "SE3" in response
    assert response["SE3"][0]["price"] == price_value


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (NordPoolAuthenticationError, "authentication_error"),
        (NordPoolError, "connection_error"),
        (TimeoutError, "connection_error"),
    ],
)
@pytest.mark.freeze_time("2025-10-01T18:00:00+00:00")
async def test_service_call_failures(
    hass: HomeAssistant,
    load_int: MockConfigEntry,
    error: Exception,
    key: str,
) -> None:
    """Test get_prices_for_date service call when it fails."""
    service_data = TEST_SERVICE_DATA.copy()
    service_data[ATTR_CONFIG_ENTRY] = load_int.entry_id

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            side_effect=error,
        ),
        pytest.raises(ServiceValidationError) as err,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRICES_FOR_DATE,
            service_data,
            blocking=True,
            return_response=True,
        )
    assert err.value.translation_key == key


@pytest.mark.freeze_time("2025-10-01T18:00:00+00:00")
async def test_empty_response_returns_empty_list(
    hass: HomeAssistant,
    load_int: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test get_prices_for_date service call return empty list for empty response."""
    service_data = TEST_SERVICE_DATA.copy()
    service_data[ATTR_CONFIG_ENTRY] = load_int.entry_id

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            side_effect=NordPoolEmptyResponseError,
        ),
    ):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRICES_FOR_DATE,
            service_data,
            blocking=True,
            return_response=True,
        )

    assert response == snapshot


@pytest.mark.freeze_time("2025-10-01T18:00:00+00:00")
async def test_service_call_config_entry_bad_state(
    hass: HomeAssistant,
    load_int: MockConfigEntry,
) -> None:
    """Test get_prices_for_date service call when config entry bad state."""

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRICES_FOR_DATE,
            TEST_SERVICE_DATA,
            blocking=True,
            return_response=True,
        )
    assert err.value.translation_key == "entry_not_found"

    service_data = TEST_SERVICE_DATA.copy()
    service_data[ATTR_CONFIG_ENTRY] = load_int.entry_id
    await hass.config_entries.async_unload(load_int.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRICES_FOR_DATE,
            service_data,
            blocking=True,
            return_response=True,
        )
    assert err.value.translation_key == "entry_not_loaded"


@pytest.mark.freeze_time("2025-10-01T18:00:00+00:00")
async def test_service_call_for_price_indices(
    hass: HomeAssistant,
    load_int: MockConfigEntry,
    snapshot: SnapshotAssertion,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test get_price_indices_for_date service call."""

    fixture_60 = json.loads(await async_load_fixture(hass, "indices_60.json", DOMAIN))
    fixture_15 = json.loads(await async_load_fixture(hass, "indices_15.json", DOMAIN))

    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPriceIndices",
        params={
            "date": "2025-10-01",
            "market": "DayAhead",
            "indexNames": "SE3",
            "currency": "SEK",
            "resolutionInMinutes": "60",
        },
        json=fixture_60,
    )

    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPriceIndices",
        params={
            "date": "2025-10-01",
            "market": "DayAhead",
            "indexNames": "SE3",
            "currency": "SEK",
            "resolutionInMinutes": "15",
        },
        json=fixture_15,
    )

    service_data = TEST_SERVICE_INDICES_DATA_60.copy()
    service_data[ATTR_CONFIG_ENTRY] = load_int.entry_id
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PRICE_INDICES_FOR_DATE,
        service_data,
        blocking=True,
        return_response=True,
    )

    assert response == snapshot(name="get_price_indices_for_date_60")

    service_data = TEST_SERVICE_INDICES_DATA_15.copy()
    service_data[ATTR_CONFIG_ENTRY] = load_int.entry_id
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PRICE_INDICES_FOR_DATE,
        service_data,
        blocking=True,
        return_response=True,
    )

    assert response == snapshot(name="get_price_indices_for_date_15")
