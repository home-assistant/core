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
