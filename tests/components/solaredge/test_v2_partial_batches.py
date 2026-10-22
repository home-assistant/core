"""Throttled batches resume only unfinished jobs; all provider data is synthetic."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.solaredge.v2_budget import get_budget
from homeassistant.components.solaredge.v2_runtime import SolarEdgeV2Coordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .test_community import register_basic
from .test_v2_runtime import coordinator, entry_data

# Arbitrary synthetic clock.
NOW = datetime(2033, 6, 7, 9, tzinfo=UTC)
CLOCK = "homeassistant.components.solaredge.v2_budget.dt_util.utcnow"
CADENCE = {
    "lifetime": 24,
    "power": 2,
    "metadata": 168,
    "inventory": 168,
    "day": 4,
    "month": 4,
    "year": 4,
    "storage": 4,
}


def _coordinator(hass: HomeAssistant) -> SolarEdgeV2Coordinator:
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    return coordinator(hass, entry)


def _paths(aioclient_mock: AiohttpClientMocker) -> list[str]:
    return sorted(call[1].path for call in aioclient_mock.mock_calls)


async def test_throttled_batch_keeps_completed_cadence(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Five reads succeed, the shared minute limit stops the rest; retry the rest."""
    budget = get_budget(hass)
    # Another entry already used half of this rolling minute.
    budget.state = {"calls": [(NOW - timedelta(seconds=30)).timestamp()] * 5}
    budget.state["blocked"] = 0
    await budget.store.async_save(budget.state)
    coord = _coordinator(hass)
    register_basic(aioclient_mock, NOW)
    with (
        patch(CLOCK, return_value=NOW),
        pytest.raises(UpdateFailed, match="quota exceeded"),
    ):
        await coord._async_update_data()
    assert aioclient_mock.call_count == 5
    retry = (NOW + timedelta(seconds=30)).timestamp()
    done = ("lifetime", "power", "metadata", "inventory", "day")
    assert coord.state["due"] == {
        **{key: (NOW + timedelta(hours=CADENCE[key])).timestamp() for key in done},
        "month": retry,
        "year": retry,
        "storage": retry,
    }
    assert coord.state["next_poll"] == retry
    # Reservations are conservative and never refunded.
    assert len(coord.state["calls"]) == 8
    assert budget.state["blocked"] == 0

    later = NOW + timedelta(minutes=2)
    aioclient_mock.clear_requests()
    register_basic(aioclient_mock, later)
    with patch(CLOCK, return_value=later):
        data = await coord._async_update_data()
    # Only the unfinished jobs are requested again.
    assert _paths(aioclient_mock) == [
        "/v2/sites/123/overview",
        "/v2/sites/123/overview",
        "/v2/sites/123/storage/lifetime-energy",
    ]
    assert data["energy_this_month"].value == 2000
    assert data["energy_this_year"].value == 2000
    assert data["storage_charge_energy"].value == 30
    # Completed readings and their cadence are kept, not re-fetched.
    assert data["lifetime_energy"].value == 12000
    assert data["lifetime_energy"].timestamp == NOW
    assert coord.state["due"]["lifetime"] == (NOW + timedelta(hours=24)).timestamp()
    assert coord.state["due"]["year"] == (later + timedelta(hours=4)).timestamp()
    assert len(coord.state["calls"]) == 11
    assert coord.state["failed"] is False


async def test_concurrent_entries_complete_every_job(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Two full batches sharing ten requests per minute finish in two rounds."""
    coords = [_coordinator(hass), _coordinator(hass)]
    requests = 0
    for minutes in (0, 2):
        when = NOW + timedelta(minutes=minutes)
        aioclient_mock.clear_requests()
        register_basic(aioclient_mock, when)
        with patch(CLOCK, return_value=when):
            await asyncio.gather(
                *(coord._async_update_data() for coord in coords),
                return_exceptions=True,
            )
        requests += aioclient_mock.call_count
    # Each of the 16 jobs ran exactly once; none was repeated or starved.
    assert requests == 16
    for coord in coords:
        assert coord.state["failed"] is False
        assert {
            "energy_this_month",
            "energy_this_year",
            "storage_charge_energy",
        } <= set(coord.state["readings"])
    assert get_budget(hass).state["blocked"] == 0
