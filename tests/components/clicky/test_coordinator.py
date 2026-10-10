"""Tests for the Clicky coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock

from pyclicky import AuthenticationError, ClickyAPIError, ConnectionError
import pytest

from homeassistant.components.clicky.const import DOMAIN
from homeassistant.components.clicky.coordinator import ClickyCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from .common import _make_report


def test_coordinator_init(hass: HomeAssistant) -> None:
    """Test coordinator initialization."""

    entry = Mock()
    client = Mock()

    coordinator = ClickyCoordinator(
        hass=hass,
        config_entry=entry,
        client=client,
    )

    assert coordinator.client is client
    assert coordinator.name == DOMAIN
    assert coordinator.update_interval == timedelta(minutes=1)


@pytest.mark.asyncio
async def test_async_update_data_auth_failure(hass: HomeAssistant) -> None:
    """Test that authentication errors become ConfigEntryAuthFailed."""

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    client.visitors_online.side_effect = AuthenticationError

    coordinator = ClickyCoordinator(
        hass=hass,
        config_entry=Mock(),
        client=client,
    )

    with pytest.raises(ConfigEntryAuthFailed, match="API authentication failed"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_async_update_data_connection_error(hass: HomeAssistant) -> None:
    """Test that connection errors become UpdateFailed."""

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    client.visitors_online.side_effect = ConnectionError

    coordinator = ClickyCoordinator(
        hass=hass,
        config_entry=Mock(),
        client=client,
    )

    with pytest.raises(UpdateFailed, match="Couldn't connect to API"):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_async_update_data_success(hass: HomeAssistant) -> None:
    """Test successful update."""

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    client.visitors_online.return_value = _make_report(12)
    client.time_total.return_value = _make_report(345)

    coordinator = ClickyCoordinator(
        hass=hass,
        config_entry=Mock(),
        client=client,
    )

    data = await coordinator._async_update_data()

    assert data == {
        "visitorsOnline": 12,
        "timeTotal": 345,
    }

    assert client.visitors_online.await_count == 1
    assert client.time_total.await_count == 1


@pytest.mark.asyncio
async def test_async_update_data_failure(hass: HomeAssistant) -> None:
    """Test that API errors become UpdateFailed."""

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    client.visitors_online.side_effect = ClickyAPIError("Unexpected Error")

    coordinator = ClickyCoordinator(
        hass=hass,
        config_entry=Mock(),
        client=client,
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
