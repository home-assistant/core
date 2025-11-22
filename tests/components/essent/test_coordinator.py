"""Test the Essent coordinator."""

from __future__ import annotations

import pytest
from essent_dynamic_pricing import (
    EssentConnectionError,
    EssentDataError,
    EssentError,
    EssentResponseError,
)

from homeassistant.components.essent.coordinator import EssentDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from tests.common import MockConfigEntry

pytestmark = [
    pytest.mark.freeze_time("2025-11-16 12:00:00+01:00"),
    pytest.mark.usefixtures("disable_coordinator_schedules"),
]


async def test_coordinator_fetch_success(
    hass: HomeAssistant, patch_essent_client, essent_normalized_data
) -> None:
    """Test successful data fetch."""
    entry = MockConfigEntry(domain="essent", data={}, unique_id="essent")
    coordinator = EssentDataUpdateCoordinator(hass, entry)

    data = await coordinator._async_update_data()

    assert data == essent_normalized_data
    elec = data.electricity
    gas = data.gas
    assert len(elec.tariffs) == 3
    assert len(elec.tariffs_tomorrow) == 1
    assert len(gas.tariffs) == 3
    assert elec.unit == "kWh"
    assert gas.unit == "m³"
    assert elec.min_price == 0.2
    assert round(elec.avg_price, 4) == 0.2233
    assert elec.max_price == 0.25


async def test_coordinator_fetch_failure(hass: HomeAssistant, patch_essent_client) -> None:
    """Test failed data fetch."""
    patch_essent_client.async_get_prices.side_effect = EssentResponseError("boom")
    entry = MockConfigEntry(domain="essent", data={}, unique_id="essent")
    coordinator = EssentDataUpdateCoordinator(hass, entry)

    with pytest.raises(UpdateFailed, match="boom"):
        await coordinator._async_update_data()


async def test_coordinator_data_error(hass: HomeAssistant, patch_essent_client) -> None:
    """Test data errors from the client."""
    patch_essent_client.async_get_prices.side_effect = EssentDataError("bad data")
    entry = MockConfigEntry(domain="essent", data={}, unique_id="essent")
    coordinator = EssentDataUpdateCoordinator(hass, entry)

    with pytest.raises(UpdateFailed, match="bad data"):
        await coordinator._async_update_data()


async def test_coordinator_connection_error(
    hass: HomeAssistant, patch_essent_client
) -> None:
    """Test connection errors raise UpdateFailed with context."""
    patch_essent_client.async_get_prices.side_effect = EssentConnectionError("fail")
    entry = MockConfigEntry(domain="essent", data={}, unique_id="essent")
    coordinator = EssentDataUpdateCoordinator(hass, entry)

    with pytest.raises(UpdateFailed, match="Error communicating with API: fail"):
        await coordinator._async_update_data()


async def test_coordinator_generic_essent_error(
    hass: HomeAssistant, patch_essent_client
) -> None:
    """Test unexpected Essent errors are wrapped."""
    patch_essent_client.async_get_prices.side_effect = EssentError("boom")
    entry = MockConfigEntry(domain="essent", data={}, unique_id="essent")
    coordinator = EssentDataUpdateCoordinator(hass, entry)

    with pytest.raises(UpdateFailed, match="Unexpected Essent error"):
        await coordinator._async_update_data()
