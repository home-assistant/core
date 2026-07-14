"""Tests for the GridX coordinators."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from homeassistant.components.gridx.const import CONF_OEM, DOMAIN
from homeassistant.components.gridx.coordinator import (
    GridxHistoricalCoordinator,
    GridxLiveCoordinator,
    _fetch_historical,
    _fetch_live,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import MOCK_HIST_DATA, MOCK_LIVE_DATA, OEM, PASSWORD, USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock GridX config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        title=USERNAME,
    )
    entry.add_to_hass(hass)
    return entry


async def test_live_coordinator_success(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that live coordinator returns processed data."""
    connector = MagicMock()
    connector.retrieve_live_data = AsyncMock(return_value=[MOCK_LIVE_DATA])

    coord = GridxLiveCoordinator(hass, config_entry, connector)
    await coord.async_refresh()

    assert coord.data["photovoltaic"] == 1512
    assert coord.data["battery"]["stateOfCharge"] == 0.77


async def test_live_coordinator_aggregates_multiple_systems(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Aggregate live data across multiple systems."""
    connector = MagicMock()
    connector.retrieve_live_data = AsyncMock(
        return_value=[
            {
                "photovoltaic": 100,
                "grid": -50,
                "selfConsumptionRate": 0.4,
                "measuredAt": "2024-05-08T09:42:18Z",
                "battery": {"power": -100, "stateOfCharge": 0.5, "capacity": 10000},
                "heatPumps": [{"power": 10}],
            },
            {
                "photovoltaic": 200,
                "grid": 30,
                "selfConsumptionRate": 0.6,
                "measuredAt": "2024-05-08T09:42:20Z",
                "battery": {"power": 40, "stateOfCharge": 0.7, "capacity": 5000},
                "heatPumps": [{"power": 20}],
            },
            {
                "photovoltaic": 50,
            },
        ]
    )

    data = await _fetch_live(connector)

    assert data["photovoltaic"] == 350
    assert data["grid"] == -20
    # Rates are averaged, not summed
    assert data["selfConsumptionRate"] == pytest.approx(0.5)
    assert data["measuredAt"] == "2024-05-08T09:42:18Z"
    # Battery values are aggregated over the systems that have a battery
    assert data["battery"]["power"] == -60
    assert data["battery"]["stateOfCharge"] == pytest.approx(0.6)
    assert data["battery"]["capacity"] == 15000
    # Lists are concatenated
    assert data["heatPumps"] == [{"power": 10}, {"power": 20}]


async def test_live_coordinator_single_system_untouched(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A single-system response is returned as-is, including rates."""
    connector = MagicMock()
    connector.retrieve_live_data = AsyncMock(return_value=[MOCK_LIVE_DATA])

    data = await _fetch_live(connector)

    assert data == MOCK_LIVE_DATA


async def test_live_coordinator_empty_response(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that an empty live response raises UpdateFailed."""
    connector = MagicMock()
    connector.retrieve_live_data = AsyncMock(return_value=[])

    coord = GridxLiveCoordinator(hass, config_entry, connector)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


async def test_live_coordinator_auth_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that a PermissionError raises ConfigEntryAuthFailed."""
    connector = MagicMock()
    connector.retrieve_live_data = AsyncMock(side_effect=PermissionError("expired"))

    with pytest.raises(ConfigEntryAuthFailed):
        await _fetch_live(connector)


async def test_historical_coordinator_success(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that historical coordinator returns total + last_reset."""
    connector = MagicMock()
    connector.retrieve_historical_data = AsyncMock(return_value=MOCK_HIST_DATA)

    coord = GridxHistoricalCoordinator(hass, config_entry, connector)
    await coord.async_refresh()

    assert coord.data["total"]["photovoltaic"] == 8500
    assert "last_reset" in coord.data


async def test_historical_coordinator_aggregates_multiple_systems(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Aggregate historical totals across multiple systems."""
    connector = MagicMock()
    connector.retrieve_historical_data = AsyncMock(
        return_value=[
            {
                "total": {
                    "photovoltaic": 100,
                    "gridMeterReadingPositive": 1.5,
                    "selfConsumptionRate": 0.4,
                    "unit": "Wh",
                    "mode": "single",
                }
            },
            {
                "total": {
                    "photovoltaic": 250,
                    "gridMeterReadingPositive": 2.5,
                    "selfConsumptionRate": 0.6,
                    "mode": 1,
                }
            },
            {"total": "invalid"},
        ]
    )

    data = await _fetch_historical(connector)

    assert data["total"]["photovoltaic"] == 350
    assert data["total"]["gridMeterReadingPositive"] == pytest.approx(4.0)
    # Rates are averaged, not summed
    assert data["total"]["selfConsumptionRate"] == pytest.approx(0.5)
    assert data["total"]["unit"] == "Wh"
    # Non-numeric first value should not be overwritten by later numeric values.
    assert data["total"]["mode"] == "single"
    assert "last_reset" in data


async def test_historical_coordinator_empty_response(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that an empty historical response raises UpdateFailed."""
    connector = MagicMock()
    connector.retrieve_historical_data = AsyncMock(return_value=[])

    with pytest.raises(UpdateFailed):
        await _fetch_historical(connector)


async def test_historical_coordinator_auth_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that a PermissionError in historical fetch raises ConfigEntryAuthFailed."""
    connector = MagicMock()
    connector.retrieve_historical_data = AsyncMock(
        side_effect=PermissionError("expired")
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await _fetch_historical(connector)


async def test_live_coordinator_http_401(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """HTTPStatusError with 401 raises ConfigEntryAuthFailed in live coordinator."""
    response = MagicMock()
    response.status_code = 401
    err = httpx.HTTPStatusError("401", request=MagicMock(), response=response)
    connector = MagicMock()
    connector.retrieve_live_data = AsyncMock(side_effect=err)

    with pytest.raises(ConfigEntryAuthFailed):
        await _fetch_live(connector)


async def test_live_coordinator_http_status_500(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """HTTPStatusError with 500 raises UpdateFailed (not auth) in live coordinator."""
    response = MagicMock()
    response.status_code = 500
    err = httpx.HTTPStatusError("500", request=MagicMock(), response=response)
    connector = MagicMock()
    connector.retrieve_live_data = AsyncMock(side_effect=err)

    with pytest.raises(UpdateFailed):
        await _fetch_live(connector)


async def test_live_coordinator_http_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """httpx.HTTPError raises UpdateFailed in live coordinator."""
    connector = MagicMock()
    connector.retrieve_live_data = AsyncMock(
        side_effect=httpx.HTTPError("connection failed")
    )

    with pytest.raises(UpdateFailed):
        await _fetch_live(connector)


async def test_live_coordinator_runtime_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """RuntimeError raises UpdateFailed in live coordinator."""
    connector = MagicMock()
    connector.retrieve_live_data = AsyncMock(side_effect=RuntimeError("unexpected"))

    with pytest.raises(UpdateFailed):
        await _fetch_live(connector)


async def test_historical_coordinator_http_401(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """HTTPStatusError with 401 raises ConfigEntryAuthFailed in historical coordinator."""
    response = MagicMock()
    response.status_code = 401
    err = httpx.HTTPStatusError("401", request=MagicMock(), response=response)
    connector = MagicMock()
    connector.retrieve_historical_data = AsyncMock(side_effect=err)

    with pytest.raises(ConfigEntryAuthFailed):
        await _fetch_historical(connector)


async def test_historical_coordinator_http_status_500(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """HTTPStatusError with 500 raises UpdateFailed in historical coordinator."""
    response = MagicMock()
    response.status_code = 500
    err = httpx.HTTPStatusError("500", request=MagicMock(), response=response)
    connector = MagicMock()
    connector.retrieve_historical_data = AsyncMock(side_effect=err)

    with pytest.raises(UpdateFailed):
        await _fetch_historical(connector)


async def test_historical_coordinator_http_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """httpx.HTTPError raises UpdateFailed in historical coordinator."""
    connector = MagicMock()
    connector.retrieve_historical_data = AsyncMock(
        side_effect=httpx.HTTPError("connection failed")
    )

    with pytest.raises(UpdateFailed):
        await _fetch_historical(connector)


async def test_historical_coordinator_runtime_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """RuntimeError raises UpdateFailed in historical coordinator."""
    connector = MagicMock()
    connector.retrieve_historical_data = AsyncMock(
        side_effect=RuntimeError("unexpected")
    )

    with pytest.raises(UpdateFailed):
        await _fetch_historical(connector)
