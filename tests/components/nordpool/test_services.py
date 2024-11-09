"""Test services in Nord Pool."""

from unittest.mock import patch

from pynordpool import DeliveryPeriodData
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nordpool.const import DOMAIN
from homeassistant.components.nordpool.services import (
    ATTR_AREAS,
    ATTR_CONFIG_ENTRY,
    ATTR_CURRENCY,
    SERVICE_GET_PRICES_FOR_DATE,
)
from homeassistant.const import ATTR_DATE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry

TEST_SERVICE_DATA = {
    ATTR_CONFIG_ENTRY: "to_replace",
    ATTR_DATE: "2024-11-05",
    ATTR_AREAS: ["SE3", "SE4"],
    ATTR_CURRENCY: "SEK",
}


@pytest.mark.freeze_time("2024-11-05T18:00:00+00:00")
async def test_service_call(
    hass: HomeAssistant,
    load_int: MockConfigEntry,
    get_data: DeliveryPeriodData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test get_prices_for_date service call."""

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            return_value=get_data,
        ),
    ):
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


@pytest.mark.freeze_time("2024-11-05T18:00:00+00:00")
async def test_service_call_failures(
    hass: HomeAssistant,
    load_int: MockConfigEntry,
    get_data: DeliveryPeriodData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test get_prices_for_date service call when it fails."""

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            return_value=get_data,
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRICES_FOR_DATE,
            TEST_SERVICE_DATA,
            blocking=True,
            return_response=True,
        )

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            return_value=get_data,
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRICES_FOR_DATE,
            TEST_SERVICE_DATA,
            blocking=True,
            return_response=True,
        )
