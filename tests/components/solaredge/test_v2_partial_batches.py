"""Throttled batches resume only unfinished jobs; all provider data is synthetic."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.solaredge.coordinator import SolarEdgeV2Coordinator
from homeassistant.components.solaredge.v2_budget import get_budget
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
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


INVENTORY_URL = "https://monitoringapi.solaredge.com/v2/sites/123/devices"
DONE = ("lifetime", "power", "metadata")
UNFINISHED = ["inventory", "day", "month", "year", "storage"]


@pytest.mark.parametrize(
    ("failure", "raised", "http_calls"),
    [
        pytest.param("provider_429", UpdateFailed, 4, id="provider-429"),
        pytest.param("auth_401", ConfigEntryAuthFailed, 4, id="auth-401"),
        pytest.param("unexpected", RuntimeError, 3, id="unexpected"),
        pytest.param("cancelled", asyncio.CancelledError, 3, id="cancelled"),
    ],
)
async def test_failure_after_partial_batch_retries_only_unfinished(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    failure: str,
    raised: type[BaseException],
    http_calls: int,
) -> None:
    """Three jobs finish, the fourth fails; finished cadence and reservations stay."""
    coord = _coordinator(hass)
    if failure == "provider_429":
        aioclient_mock.get(
            INVENTORY_URL,
            status=429,
            headers={"Retry-After": "7200", "x-ratelimit-remaining-month": "0"},
        )
    elif failure == "auth_401":
        aioclient_mock.get(INVENTORY_URL, status=401)
    else:
        error = RuntimeError("synthetic") if failure == "unexpected" else None
        coord.api.inventory = AsyncMock(side_effect=error or asyncio.CancelledError())
    register_basic(aioclient_mock, NOW)
    with patch(CLOCK, return_value=NOW), pytest.raises(raised):
        await coord._async_update_data()
    # The scheduled save after cancellation/unexpected errors is drained.
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == http_calls
    saved = await coord.store.async_load()
    assert saved == coord.state
    retry = saved["next_poll"]
    assert saved["due"] == {
        **{key: (NOW + timedelta(hours=CADENCE[key])).timestamp() for key in DONE},
        **dict.fromkeys(UNFINISHED, retry),
    }
    assert saved["failed"] is True
    assert len(saved["calls"]) == 8
    assert saved["readings"]["lifetime_energy"]["value"] == 12000
    budget = get_budget(hass).state
    if failure == "provider_429":
        assert retry == (NOW + timedelta(hours=2)).timestamp()
        assert budget["blocked"] == retry
        assert saved["quota_kind"] == "monthly"
    else:
        assert budget["blocked"] == 0
        assert retry == (NOW + timedelta(hours=2)).timestamp()
    if failure == "auth_401":
        assert saved["auth_failed_jobs"] == UNFINISHED
    else:
        assert "auth_failed_jobs" not in saved


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
