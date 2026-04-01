"""Tests for the GridX coordinators."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.gridx.coordinator import (
    GridxHistoricalCoordinator,
    GridxLiveCoordinator,
)
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry

from .conftest import MOCK_HIST_DATA, MOCK_LIVE_DATA, OEM, PASSWORD, USERNAME


@pytest.fixture
def config_entry(hass):
    """Return a mock GridX config entry."""
    from homeassistant.components.gridx.const import CONF_OEM, DOMAIN
    from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        title=USERNAME,
    )
    entry.add_to_hass(hass)
    return entry


async def test_live_coordinator_success(hass, config_entry) -> None:
    """Test that live coordinator returns processed data."""
    connector = MagicMock()
    connector.retrieve_live_data = AsyncMock(return_value=[MOCK_LIVE_DATA])

    coord = GridxLiveCoordinator(hass, config_entry, connector)
    await coord.async_refresh()

    assert coord.data["photovoltaic"] == 1512
    assert coord.data["battery"]["stateOfCharge"] == 0.77


async def test_live_coordinator_empty_response(hass, config_entry) -> None:
    """Test that an empty live response raises UpdateFailed."""
    connector = MagicMock()
    connector.retrieve_live_data = AsyncMock(return_value=[])

    coord = GridxLiveCoordinator(hass, config_entry, connector)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()  # noqa: SLF001


async def test_live_coordinator_auth_error(hass, config_entry) -> None:
    """Test that a PermissionError raises ConfigEntryAuthFailed."""
    from homeassistant.components.gridx.coordinator import _fetch_live

    connector = MagicMock()
    connector.retrieve_live_data = AsyncMock(side_effect=PermissionError("expired"))

    with pytest.raises(ConfigEntryAuthFailed):
        await _fetch_live(connector)


async def test_historical_coordinator_success(hass, config_entry) -> None:
    """Test that historical coordinator returns total + last_reset."""
    connector = MagicMock()
    connector.retrieve_historical_data = AsyncMock(return_value=MOCK_HIST_DATA)

    coord = GridxHistoricalCoordinator(hass, config_entry, connector)
    await coord.async_refresh()

    assert coord.data["total"]["photovoltaic"] == 8500
    assert "last_reset" in coord.data


async def test_historical_coordinator_empty_response(hass, config_entry) -> None:
    """Test that an empty historical response raises UpdateFailed."""
    from homeassistant.components.gridx.coordinator import _fetch_historical

    connector = MagicMock()
    connector.retrieve_historical_data = AsyncMock(return_value=[])

    with pytest.raises(UpdateFailed):
        await _fetch_historical(connector)


async def test_historical_coordinator_auth_error(hass, config_entry) -> None:
    """Test that a PermissionError in historical fetch raises ConfigEntryAuthFailed."""
    from homeassistant.components.gridx.coordinator import _fetch_historical

    connector = MagicMock()
    connector.retrieve_historical_data = AsyncMock(side_effect=PermissionError("expired"))

    with pytest.raises(ConfigEntryAuthFailed):
        await _fetch_historical(connector)
