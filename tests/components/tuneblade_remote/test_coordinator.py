"""Test coordinator for the TuneBlade Remote integration."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
import pytest

from homeassistant.components.tuneblade_remote.coordinator import (
    TuneBladeDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.mark.asyncio
async def test_async_init_success(hass: HomeAssistant) -> None:
    """Test async_init calls first refresh successfully."""
    client = AsyncMock()
    client.async_get_data = AsyncMock(return_value=[{"id": "device1"}])
    coordinator = TuneBladeDataUpdateCoordinator(hass, client)

    coordinator.async_config_entry_first_refresh = AsyncMock()
    await coordinator.async_init()
    coordinator.async_config_entry_first_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_init_raises_config_entry_not_ready(hass: HomeAssistant) -> None:
    """Test async_init raises ConfigEntryNotReady on connection errors."""
    client = AsyncMock()
    coordinator = TuneBladeDataUpdateCoordinator(hass, client)
    coordinator.async_config_entry_first_refresh = AsyncMock(
        side_effect=UpdateFailed("fail")
    )

    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_init()


@pytest.mark.asyncio
async def test_async_update_data_success(hass: HomeAssistant) -> None:
    """Test _async_update_data returns device data successfully."""
    client = AsyncMock()
    client.async_get_data = AsyncMock(
        return_value=[{"id": "device1", "name": "TestDevice"}]
    )
    coordinator = TuneBladeDataUpdateCoordinator(hass, client)

    result = await coordinator._async_update_data()
    assert isinstance(result, list)
    assert result[0]["id"] == "device1"


@pytest.mark.asyncio
async def test_async_update_data_raises_update_failed_on_empty(
    hass: HomeAssistant,
) -> None:
    """Test _async_update_data raises UpdateFailed if empty data returned."""
    client = AsyncMock()
    client.async_get_data = AsyncMock(return_value=[])
    coordinator = TuneBladeDataUpdateCoordinator(hass, client)

    with pytest.raises(
        UpdateFailed, match="No device data returned from TuneBlade hub."
    ):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_async_update_data_raises_update_failed_on_client_error(
    hass: HomeAssistant,
) -> None:
    """Test _async_update_data raises UpdateFailed on ClientError."""
    client = AsyncMock()
    client.async_get_data = AsyncMock(side_effect=ClientError("connection error"))
    coordinator = TuneBladeDataUpdateCoordinator(hass, client)

    with pytest.raises(UpdateFailed, match="Error communicating with TuneBlade hub:"):
        await coordinator._async_update_data()
