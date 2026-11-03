"""Tests for the Tankerkoenig services."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from aiotankerkoenig import (
    Station,
    TankerkoenigConnectionError,
    TankerkoenigError,
    TankerkoenigInvalidKeyError,
    TankerkoenigRateLimitError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.tankerkoenig.const import DOMAIN
from homeassistant.components.tankerkoenig.services import TankerkoenigService
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.exceptions import HomeAssistantError

from .const import STATION

ENTITY_ID = "binary_sensor.station_somewhere_street_1_status"
OVERRIDE = "24.12.2026, 14:00:00 - 26.12.2026, 23:59:00: geschlossen"


async def get_opening_times(hass: HomeAssistant) -> ServiceResponse:
    """Call the action for the test station."""
    return await hass.services.async_call(
        DOMAIN,
        TankerkoenigService.GET_OPENING_TIMES,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
        return_response=True,
    )


@pytest.mark.parametrize(
    "station",
    [
        pytest.param(STATION, id="opening_times"),
        pytest.param(
            replace(STATION, whole_day=True, opening_times=[]), id="whole_day"
        ),
        pytest.param(replace(STATION, opening_times=[]), id="no_opening_times"),
        pytest.param(replace(STATION, overrides=[OVERRIDE]), id="overrides"),
        pytest.param(
            replace(STATION, opening_times=None, overrides=None), id="missing_lists"
        ),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_get_opening_times(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the opening times and overrides of a station are returned."""
    assert await get_opening_times(hass) == snapshot


@pytest.mark.usefixtures("setup_integration")
async def test_get_opening_times_refreshes_station_details(
    hass: HomeAssistant,
    tankerkoenig: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the station details are fetched again once they are an hour old."""
    changed: Station = replace(STATION, overrides=[OVERRIDE])
    tankerkoenig.station_details.return_value = changed
    tankerkoenig.station_details.reset_mock()

    freezer.tick(timedelta(minutes=59))
    response = await get_opening_times(hass)
    assert response[ENTITY_ID]["overrides"] == []
    tankerkoenig.station_details.assert_not_called()

    freezer.tick(timedelta(minutes=1))
    response = await get_opening_times(hass)
    assert response[ENTITY_ID]["overrides"] == [OVERRIDE]
    tankerkoenig.station_details.assert_called_once_with(STATION.id)

    response = await get_opening_times(hass)
    assert response[ENTITY_ID]["overrides"] == [OVERRIDE]
    tankerkoenig.station_details.assert_called_once()


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        pytest.param(
            TankerkoenigInvalidKeyError("invalid key"),
            "invalid_api_key",
            id="invalid_key",
        ),
        pytest.param(
            TankerkoenigRateLimitError("rate limit"),
            "rate_limit_reached",
            id="rate_limit",
        ),
        pytest.param(
            TankerkoenigConnectionError("connection"),
            "connection_error",
            id="connection",
        ),
        pytest.param(
            TankerkoenigError("unknown"), "station_update_failed", id="unknown"
        ),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_get_opening_times_fetch_fails(
    hass: HomeAssistant,
    tankerkoenig: AsyncMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test a failed fetch of the station details raises a translated error."""
    tankerkoenig.station_details.side_effect = exception
    freezer.tick(timedelta(hours=1))

    with pytest.raises(HomeAssistantError) as err:
        await get_opening_times(hass)
    assert err.value.translation_key == translation_key
