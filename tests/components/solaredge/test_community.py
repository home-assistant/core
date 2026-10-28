"""Community acceptance: real native client, sensors, cache and shared budget."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiosolaredge.monitoring import period_start
from aiosolaredge.v2 import PermissionDeniedError, RateLimitError, Reading
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.components.solaredge.application_credentials import (
    async_get_auth_implementation,
)
from homeassistant.components.solaredge.sensor import (
    SENSOR_TYPES,
    SUPPORTED,
    SolarEdgeV2Sensor,
)
from homeassistant.components.solaredge.v2_budget import (
    MAX_CALLS,
    SolarEdgeBudget,
    get_budget,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestTransientError
from homeassistant.util import dt as dt_util

from .test_v2_runtime import BASE, coordinator, entry_data


def register_basic(mock, now):
    """Synthetic official shapes only; no network permitted by HA test fixture."""
    mock.get(
        BASE + "/sites/123",
        json={
            "siteId": 123,
            "activationStatus": "ACTIVE",
            "location": {"timezone": "Europe/Amsterdam", "address": "PRIVATE"},
            "name": "Synthetic",
        },
    )
    mock.get(
        BASE + "/sites/123/devices", json=[{"type": "BATTERY", "serialNumber": "B1"}]
    )
    mock.get(
        BASE + "/sites/123/lifetime-energy",
        json={"energy": 12, "unit": "KWH", "lastUpdateTime": now.isoformat()},
    )
    mock.get(
        BASE + "/sites/123/power",
        json={
            "unit": "W",
            "resolution": "QUARTER_HOUR",
            "values": [
                {"timestamp": (now - timedelta(minutes=15)).isoformat(), "value": 42}
            ],
        },
    )
    mock.get(
        BASE + "/sites/123/overview",
        json={
            "siteId": 123,
            "production": {
                "unit": "KWH",
                "total": 2,
                "toGrid": 0,
                "toSelfConsumption": None,
            },
            "consumption": {"unit": "WH", "total": None, "fromGrid": 3},
        },
    )
    samples = [
        {"timestamp": (now - timedelta(minutes=15)).isoformat(), "value": 100},
        {"timestamp": now.isoformat(), "value": 130},
    ]
    mock.get(
        BASE + "/sites/123/storage/lifetime-energy",
        json={
            "batteries": [
                {
                    "serialNumber": "B1",
                    "unit": "WH",
                    "lifetimeEnergyCharged": samples,
                    "lifetimeEnergyDischarged": samples,
                }
            ]
        },
    )


async def test_community_complete_poll_identity_cache(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Every equivalent native site reading is mapped; no paid endpoint is requested."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    now = dt_util.utcnow().replace(hour=12)
    register_basic(aioclient_mock, now)
    coord = coordinator(hass, entry)
    with patch(
        "homeassistant.components.solaredge.coordinator.dt_util.utcnow",
        return_value=now,
    ):
        data = await coord._async_update_data()
        assert len(aioclient_mock.mock_calls) == 8
        assert data["energy_today"].value == 2000
        assert data["energy_this_month"].value == 2000
        assert data["energy_this_year"].value == 2000
        assert data["purchased_energy"].value == 3
        assert data["feedin_energy"].value == 0
        assert data["consumption_energy"].value is None
        assert data["storage_charge_energy"].value == 30
        assert data["B1_battery_discharge_energy"].value == 30
        assert "address" not in str(coord.state)
        coord.async_set_updated_data(data)
        for description in SENSOR_TYPES:
            if description.key in SUPPORTED:
                sensor = SolarEdgeV2Sensor(coord, description)
                assert sensor.unique_id == (
                    "123"
                    if description.key == "site_details"
                    else f"123_{description.key}"
                )
                assert sensor.entity_description is description
                if description.key == "site_details":
                    assert sensor.native_value == "active"
                if description.key == "energy_today":
                    assert (
                        sensor.extra_state_attributes["timestamp_semantics"]
                        == "requested_range_not_source_sample"
                    )
        restored = coordinator(hass, entry)
        await restored._async_setup()
        assert await restored._async_update_data() == data
        assert aioclient_mock.call_count == 8
        assert len(get_budget(hass).state["calls"]) == 8


async def test_device_scope_denial_keeps_production(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A SITE_DATA-only existing grant does not force renewed consent."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    now = dt_util.utcnow().replace(hour=12)
    register_basic(aioclient_mock, now)
    coord = coordinator(hass, entry)
    coord.api.inventory = AsyncMock(side_effect=PermissionDeniedError())
    with patch(
        "homeassistant.components.solaredge.coordinator.dt_util.utcnow",
        return_value=now,
    ):
        data = await coord._async_update_data()
    assert data["energy_today"].value == 2000
    assert data["lifetime_energy"].value == 12000
    assert coord.state["inventory"] is None
    assert coord.state["permissions"]["inventory"] == "denied"


async def test_denied_metadata_not_old_active_status(hass: HomeAssistant) -> None:
    """A failed metadata permission check must not present stale ACTIVE as current."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    coord = coordinator(hass, entry)
    coord.state["metadata"] = {"activationStatus": "ACTIVE"}
    coord.state["permissions"] = {"metadata": "denied"}
    description = next(item for item in SENSOR_TYPES if item.key == "site_details")
    assert SolarEdgeV2Sensor(coord, description).native_value is None


async def test_calendar_rollover_unknown_not_previous_day(hass: HomeAssistant) -> None:
    """Cached calendar values must not leak yesterday into today's recorder series."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    coord = coordinator(hass, entry)
    now = dt_util.utcnow().replace(hour=12)
    coord.state["metadata"] = {"timezone": "Europe/Amsterdam"}
    coord._save_readings(
        {"energy_today": Reading(15, now), "energy_this_year": Reading(123, now)}, now
    )
    with patch(
        "homeassistant.components.solaredge.coordinator.dt_util.utcnow",
        return_value=now + timedelta(days=1),
    ):
        assert coord._cached()["energy_today"].value is None
        assert coord._cached()["energy_this_year"].value == 123
    assert (
        coord.state["periods"]["energy_today"]
        == period_start(now, "Europe/Amsterdam", "day").isoformat()
    )


async def test_shared_budget_concurrency_restart_and_quota(hass: HomeAssistant) -> None:
    """One pool across entries, serialized CPM, monthly cap and durable provider pause."""
    budget = get_budget(hass)
    results = await asyncio.gather(
        *(budget.reserve() for _ in range(12)), return_exceptions=True
    )
    assert sum(isinstance(result, RateLimitError) for result in results) == 2
    assert len(budget.state["calls"]) == 10
    restored = SolarEdgeBudget(hass)
    with pytest.raises(RateLimitError):
        await restored.reserve()
    await budget.pause(
        RateLimitError(
            "7200",
            monthly_exhausted=True,
            quota={"x-ratelimit-remaining-month": 0},
            http_status=429,
        )
    )
    restored = SolarEdgeBudget(hass)
    with pytest.raises(RateLimitError):
        await restored.reserve()
    assert restored.state["quota"]["x-ratelimit-remaining-month"] == 0
    now = dt_util.utcnow().timestamp()
    budget.state = {"calls": [now - 120] * MAX_CALLS, "blocked": 0}
    await budget.store.async_save(budget.state)
    with pytest.raises(RateLimitError):
        await budget.reserve()


async def test_old_trial_storage_migration_and_stale_power(hass: HomeAssistant) -> None:
    """Read old cache without deleting reservations or relabeling current_power."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    now = dt_util.utcnow()
    coord = coordinator(hass, entry)
    await coord.store.async_save(
        {
            "calls": [now.timestamp()],
            "next_poll": (now + timedelta(hours=1)).timestamp(),
            "failed": False,
            "failures": 0,
            "readings": {
                "average_power": {
                    "value": 42,
                    "timestamp": (now - timedelta(hours=5)).isoformat(),
                }
            },
        }
    )
    await coord._async_setup()
    assert (await coord._async_update_data())["average_power"].value is None
    assert len(coord.state["calls"]) == 1
    assert coord.state["inventory"] is None
    budget = get_budget(hass)
    assert len(budget.state["calls"]) == 1
    await coord._async_setup()
    assert len(budget.state["calls"]) == 1


async def test_token_budget_no_network_when_paused(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Refresh and code exchange share persisted backoff with data/setup reads."""
    implementation = await async_get_auth_implementation(
        hass, "solaredge", ClientCredential("synthetic", "synthetic")
    )
    await get_budget(hass).pause(RateLimitError("7200", http_status=429))
    with pytest.raises(OAuth2TokenRequestTransientError):
        await implementation._token_request(
            {"grant_type": "refresh_token", "refresh_token": "synthetic"}
        )
    assert aioclient_mock.call_count == 0
