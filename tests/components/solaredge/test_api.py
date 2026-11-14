"""Tests for the SolarEdge V2 API client."""

import asyncio
from datetime import date, datetime, timedelta
import time
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.solaredge.api import (
    SolarEdgeConnectionError,
    SolarEdgeRateLimitError,
    SolarEdgeV2,
    _latest_storage_values,
)
from homeassistant.components.solaredge.const import (
    API_BASE_URL,
    CONF_SITE_ID,
    DOMAIN,
    OAUTH2_TOKEN,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .conftest import SITE_ID


async def test_get_overview_translates_v2_data(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test V2 responses are translated without changing entity semantics."""

    async def async_access_token() -> str:
        return "access-token"

    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/overview",
        json={
            "production": {
                "total": 2.5,
                "units": "KWH",
                "toSelfConsumption": 1.0,
                "toGrid": 1.5,
            },
            "consumption": {
                "total": 1.8,
                "units": "KWH",
                "fromGrid": 0.8,
            },
        },
    )
    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/energy",
        json={"unit": "KWH", "values": [{"value": 12.0}]},
    )
    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/lifetime-energy",
        json={"energy": 4.2, "unit": "MWH"},
    )
    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/meters/telemetry",
        json={
            "meters": [
                {
                    "telemetry": [
                        {
                            "productionPower": 1234,
                            "consumptionPower": 900,
                            "importPower": 0,
                            "exportPower": 334,
                        }
                    ]
                }
            ]
        },
    )

    api = SolarEdgeV2(async_get_clientsession(hass), async_access_token)
    result = await api.get_overview(SITE_ID)

    assert result["overview"]["lifeTimeData"]["energy"] == 4_200_000
    assert result["overview"]["lastDayData"]["energy"] == 2500
    assert result["overview"]["currentPower"]["power"] == 1234


async def test_rate_limit_error_distinguishes_monthly_limit(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test monthly credit exhaustion is distinguishable from CPM limiting."""

    async def async_access_token() -> str:
        return "access-token"

    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}",
        status=429,
        headers={"x-ratelimit-remaining-minute": "7"},
        json={"message": "Monthly credit limit reached."},
    )
    api = SolarEdgeV2(async_get_clientsession(hass), async_access_token)

    with pytest.raises(SolarEdgeRateLimitError) as exc_info:
        await api.get_details(SITE_ID)

    assert exc_info.value.monthly_limit
    assert exc_info.value.retry_after is not None
    assert exc_info.value.retry_after > 0


async def test_rate_limit_without_headers_is_transient(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test an unspecified 429 does not disable requests for the month."""

    async def async_access_token() -> str:
        return "access-token"

    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}",
        status=429,
        json={"message": "Too many requests."},
    )
    api = SolarEdgeV2(async_get_clientsession(hass), async_access_token)

    with pytest.raises(SolarEdgeRateLimitError) as exc_info:
        await api.get_details(SITE_ID)

    assert not exc_info.value.monthly_limit
    assert exc_info.value.retry_after is None


async def test_get_inventory_accepts_top_level_device_list(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the documented top-level V2 device list."""

    async def async_access_token() -> str:
        return "access-token"

    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/devices",
        json=[
            {"type": "INVERTER", "serialNumber": "inverter-1"},
            {"type": "BATTERY", "serialNumber": "battery-1"},
            {"type": "METER", "serialNumber": "meter-1"},
            {"type": "METER", "serialNumber": "meter-1"},
            {"type": "METER", "serialNumber": None},
        ],
    )
    api = SolarEdgeV2(async_get_clientsession(hass), async_access_token)

    result = await api.get_inventory(SITE_ID)

    assert result["Inventory"]["inverters"][0]["SN"] == "inverter-1"
    assert result["Inventory"]["batteries"][0]["SN"] == "battery-1"
    assert result["Inventory"]["meters"] == [
        {"type": "METER", "serialNumber": "meter-1", "SN": "meter-1"}
    ]


async def test_power_flow_accepts_serial_keyed_telemetry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the documented serial-keyed meter and storage responses."""

    async def async_access_token() -> str:
        return "access-token"

    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/devices",
        json=[{"type": "BATTERY", "serialNumber": "battery-1"}],
    )
    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/meters/telemetry",
        json={
            "meters": {
                "meter-1": {
                    "productionPower": {
                        "unit": "W",
                        "values": [
                            {"timestamp": "2026-10-21T12:00:00Z", "value": 2500},
                            {"timestamp": "2026-10-21T12:15:00Z", "value": None},
                        ],
                    },
                    "consumptionPower": {
                        "unit": "W",
                        "values": [
                            {"timestamp": "2026-10-21T12:00:00Z", "value": 1800}
                        ],
                    },
                    "exportPower": {
                        "unit": "W",
                        "values": [{"timestamp": "2026-10-21T12:00:00Z", "value": 700}],
                    },
                }
            }
        },
    )
    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/storage/telemetry",
        json={
            "storage": {
                "battery-1": {
                    "chargePower": {
                        "unit": "W",
                        "values": [{"timestamp": "2026-10-21T12:00:00Z", "value": 300}],
                    },
                    "dischargePower": {
                        "unit": "W",
                        "values": [{"timestamp": "2026-10-21T12:00:00Z", "value": 0}],
                    },
                    "stateOfEnergy": {
                        "unit": "%",
                        "values": [{"timestamp": "2026-10-21T12:00:00Z", "value": 65}],
                    },
                }
            }
        },
    )
    api = SolarEdgeV2(async_get_clientsession(hass), async_access_token)
    await api.get_inventory(SITE_ID)

    result = await api.get_current_power_flow(SITE_ID)

    power_flow = result["siteCurrentPowerFlow"]
    assert power_flow["PV"]["currentPower"] == 2500
    assert power_flow["LOAD"]["currentPower"] == 1800
    assert power_flow["GRID"]["currentPower"] == 700
    assert power_flow["STORAGE"]["currentPower"] == 300
    assert power_flow["STORAGE"]["chargeLevel"] == 65
    assert {"from": "PV", "to": "GRID"} in power_flow["connections"]
    assert {"from": "PV", "to": "STORAGE"} in power_flow["connections"]


async def test_power_flow_falls_back_to_site_power(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test PV power comes from the site endpoint when meters omit production."""

    async def async_access_token() -> str:
        return "access-token"

    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/meters/telemetry",
        json={
            "meters": {
                "meter-1": {
                    "consumptionPower": {"values": [{"value": 500}]},
                    "importPower": {"values": [{"value": 200}]},
                }
            }
        },
    )
    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/power",
        json={"values": [{"value": 700}, {"value": None}]},
    )
    api = SolarEdgeV2(async_get_clientsession(hass), async_access_token)

    result = await api.get_current_power_flow(SITE_ID)

    assert result["siteCurrentPowerFlow"]["PV"]["currentPower"] == 700


async def test_concurrent_cache_misses_are_coalesced(
    hass: HomeAssistant,
) -> None:
    """Test concurrent requests for one resource use a single API call."""

    async def async_access_token() -> str:
        return "access-token"

    api = SolarEdgeV2(async_get_clientsession(hass), async_access_token)
    api._request = AsyncMock(return_value={"site": {"siteId": SITE_ID}})

    await asyncio.gather(api.get_details(SITE_ID), api.get_details(SITE_ID))

    api._request.assert_awaited_once()


async def test_dated_cache_entries_are_retired() -> None:
    """Test dated cache entries and their locks do not accumulate."""

    async def async_access_token() -> str:
        return "access-token"

    api = SolarEdgeV2(AsyncMock(), async_access_token)
    api._request = AsyncMock(return_value={})

    await api._cached_request(
        f"overview:{SITE_ID}:day:2026-10-21",
        timedelta(hours=1),
        "/overview",
    )
    api._cache_locks[f"overview:{SITE_ID}:day:2026-10-20"] = asyncio.Lock()
    await api._cached_request(
        f"overview:{SITE_ID}:day:2026-10-22",
        timedelta(hours=1),
        "/overview",
    )

    assert set(api._cache) == {f"overview:{SITE_ID}:day:2026-10-22"}
    assert set(api._cache_locks) == {f"overview:{SITE_ID}:day:2026-10-22"}


async def test_request_timeout_is_mapped(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test request timeouts use the integration connection error."""

    async def async_access_token() -> str:
        return "access-token"

    aioclient_mock.get(f"{API_BASE_URL}/sites/{SITE_ID}", exc=TimeoutError())
    api = SolarEdgeV2(async_get_clientsession(hass), async_access_token)

    with pytest.raises(SolarEdgeConnectionError):
        await api.get_details(SITE_ID)


async def test_empty_meter_response_does_not_disable_future_polling(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a temporary empty meter response is retried later."""

    async def async_access_token() -> str:
        return "access-token"

    url = f"{API_BASE_URL}/sites/{SITE_ID}/meters/telemetry"
    aioclient_mock.get(url, json={"meters": []})
    api = SolarEdgeV2(async_get_clientsession(hass), async_access_token)
    now = datetime.fromisoformat("2026-10-21T12:15:00+00:00")

    assert await api._get_meter_telemetry(SITE_ID, now) == {"meters": []}
    assert api._meter_supported


async def test_lifetime_energy_is_interpolated() -> None:
    """Test lifetime energy increases between provider refreshes."""

    async def async_access_token() -> str:
        return "access-token"

    api = SolarEdgeV2(AsyncMock(), async_access_token)
    current_day = date(2026, 10, 21)

    assert api._estimated_lifetime_energy(1_000, 100, current_day, True) == 1_000
    assert api._estimated_lifetime_energy(1_000, 125, current_day, False) == 1_025
    assert api._estimated_lifetime_energy(1_000, 10, date(2026, 10, 22), False) == 1_035


async def test_missing_daily_energy_preserves_lifetime_baseline() -> None:
    """Test a missing daily sample does not reset or inflate the baseline."""

    async def async_access_token() -> str:
        return "access-token"

    api = SolarEdgeV2(AsyncMock(), async_access_token)
    current_day = date(2026, 10, 21)

    assert api._estimated_lifetime_energy(1_000, 100, current_day, True) == 1_000
    assert api._estimated_lifetime_energy(1_000, 125, current_day, False) == 1_025
    assert api._estimated_lifetime_energy(1_000, None, current_day, False) == 1_025
    assert api._estimated_lifetime_energy(1_000, 130, current_day, False) == 1_030


async def test_missing_daily_energy_after_refresh_sets_next_baseline() -> None:
    """Test the first valid daily sample after a missing refresh is a baseline."""

    async def async_access_token() -> str:
        return "access-token"

    api = SolarEdgeV2(AsyncMock(), async_access_token)
    current_day = date(2026, 10, 21)

    assert api._estimated_lifetime_energy(1_000, None, current_day, True) == 1_000
    assert api._estimated_lifetime_energy(1_000, 100, current_day, False) == 1_000
    assert api._estimated_lifetime_energy(1_000, 125, current_day, False) == 1_025


async def test_invalid_zero_lifetime_is_not_interpolated() -> None:
    """Test a zero provider lifetime does not create a false reset."""

    async def async_access_token() -> str:
        return "access-token"

    api = SolarEdgeV2(AsyncMock(), async_access_token)
    api._get_overview = AsyncMock(
        return_value={"production": {"total": 100, "units": "WH"}}
    )
    api._get_energy = AsyncMock(return_value={"total": 100, "unit": "WH"})
    api._cached_request_with_status = AsyncMock(
        return_value=({"energy": 0, "unit": "WH"}, True)
    )
    api._get_meter_telemetry = AsyncMock(return_value={})
    api._get_site_power = AsyncMock(return_value={})

    result = await api.get_overview(SITE_ID)

    assert result["overview"]["lifeTimeData"]["energy"] is None


async def test_missing_power_remains_unknown(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test absent power samples remain unknown instead of becoming zero."""

    async def async_access_token() -> str:
        return "access-token"

    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/meters/telemetry",
        json={"meters": []},
    )
    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/power",
        json={"values": [{"value": None}]},
    )
    api = SolarEdgeV2(async_get_clientsession(hass), async_access_token)

    result = await api.get_current_power_flow(SITE_ID)

    assert result["siteCurrentPowerFlow"]["PV"]["currentPower"] is None


async def test_overview_missing_power_remains_unknown() -> None:
    """Test the overview also preserves an absent power reading."""

    async def async_access_token() -> str:
        return "access-token"

    api = SolarEdgeV2(AsyncMock(), async_access_token)
    api._get_overview = AsyncMock(return_value={"production": {}})
    api._get_energy = AsyncMock(return_value={})
    api._cached_request_with_status = AsyncMock(
        return_value=({"energy": 1_000, "unit": "WH"}, True)
    )
    api._get_meter_telemetry = AsyncMock(return_value={})
    api._get_site_power = AsyncMock(return_value={"values": [{"value": None}]})

    result = await api.get_overview(SITE_ID)

    assert result["overview"]["currentPower"]["power"] is None


async def test_power_flow_uses_net_grid_and_storage_power(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test simultaneous import/export and charge/discharge are netted."""

    async def async_access_token() -> str:
        return "access-token"

    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/devices",
        json=[{"type": "BATTERY", "serialNumber": "battery-1"}],
    )
    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/meters/telemetry",
        json={
            "meters": {
                "meter-1": {
                    "productionPower": {"values": [{"value": 500}]},
                    "importPower": {"values": [{"value": 300}]},
                    "exportPower": {"values": [{"value": 200}]},
                }
            }
        },
    )
    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/storage/telemetry",
        json={
            "storage": {
                "battery-1": {
                    "chargePower": {"values": [{"timestamp": "1", "value": 300}]},
                    "dischargePower": {"values": [{"timestamp": "1", "value": 100}]},
                }
            }
        },
    )
    api = SolarEdgeV2(async_get_clientsession(hass), async_access_token)
    await api.get_inventory(SITE_ID)

    result = await api.get_current_power_flow(SITE_ID)

    power_flow = result["siteCurrentPowerFlow"]
    assert power_flow["GRID"]["currentPower"] == 100
    assert {"from": "GRID", "to": "Load"} in power_flow["connections"]
    assert power_flow["STORAGE"]["currentPower"] == 200
    assert power_flow["STORAGE"]["status"] == "Charging"


async def test_power_flow_exposes_storage_level_without_power() -> None:
    """Test storage charge level is available without a power sample."""

    async def async_access_token() -> str:
        return "access-token"

    api = SolarEdgeV2(AsyncMock(), async_access_token)
    api._cache[f"devices:{SITE_ID}"] = (
        0,
        [{"type": "BATTERY", "serialNumber": "battery-1"}],
    )
    api._get_meter_telemetry = AsyncMock(return_value={})
    api._get_site_power = AsyncMock(return_value={})
    api._get_storage_telemetry = AsyncMock(
        return_value={
            "storage": {
                "battery-1": {
                    "stateOfEnergy": {"values": [{"timestamp": "1", "value": 60}]}
                }
            }
        }
    )

    result = await api.get_current_power_flow(SITE_ID)

    assert result["siteCurrentPowerFlow"]["STORAGE"] == {
        "status": None,
        "currentPower": None,
        "chargeLevel": 60,
    }


async def test_storage_telemetry_is_sorted_and_preserves_unknown_counters(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test storage samples are chronological and absent counters stay unknown."""

    async def async_access_token() -> str:
        return "access-token"

    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/storage/telemetry",
        json={
            "storage": {
                "battery-1": {
                    "stateOfEnergy": {
                        "values": [
                            {"timestamp": "2026-10-21T12:15:00Z", "value": 60},
                            {"timestamp": "2026-10-21T12:00:00Z", "value": 55},
                        ]
                    }
                }
            }
        },
    )
    api = SolarEdgeV2(async_get_clientsession(hass), async_access_token)

    result = await api.get_storage_data(
        SITE_ID,
        datetime.fromisoformat("2026-10-21T00:00:00+00:00"),
        datetime.fromisoformat("2026-10-21T12:15:00+00:00"),
    )

    samples = result["storageData"]["batteries"][0]["telemetries"]
    assert [sample["timeStamp"] for sample in samples] == [
        "2026-10-21T12:00:00Z",
        "2026-10-21T12:15:00Z",
    ]
    assert samples[-1]["lifeTimeEnergyCharged"] is None
    assert samples[-1]["lifeTimeEnergyDischarged"] is None


def test_multiple_battery_percentage_is_not_order_dependent() -> None:
    """Test multiple battery percentages do not create a false aggregate."""
    data = {
        "storage": {
            "battery-1": {
                "stateOfEnergy": {"values": [{"timestamp": "1", "value": 20}]}
            },
            "battery-2": {
                "stateOfEnergy": {"values": [{"timestamp": "1", "value": 80}]}
            },
        }
    }

    assert _latest_storage_values(data) == (None, None, None)


def test_multiple_battery_percentage_stays_unknown_when_one_is_missing() -> None:
    """Test one available percentage is not treated as a site aggregate."""
    data = {
        "storage": {
            "battery-1": {
                "stateOfEnergy": {"values": [{"timestamp": "1", "value": 20}]}
            },
            "battery-2": {
                "chargePower": {"values": [{"timestamp": "1", "value": 100}]}
            },
        }
    }

    assert _latest_storage_values(data) == (100, None, None)


def test_storage_metrics_use_latest_independent_samples() -> None:
    """Test each storage metric uses its latest non-null sample."""
    data = {
        "storage": {
            "battery-1": {
                "chargePower": {"values": [{"timestamp": "1", "value": 100}]},
                "stateOfEnergy": {"values": [{"timestamp": "2", "value": 60}]},
            }
        }
    }

    assert _latest_storage_values(data) == (100, None, 60)


async def test_rotated_refresh_token_is_persisted(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
) -> None:
    """Test every rotated refresh token is stored in the config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SolarEdge",
        unique_id=SITE_ID,
        data={
            CONF_SITE_ID: SITE_ID,
            "auth_implementation": DOMAIN,
            CONF_TOKEN: {
                "access_token": "expired-access-token",
                "refresh_token": "old-refresh-token",
                "expires_at": time.time() - 60,
                "expires_in": 7200,
            },
        },
        version=2,
    )
    entry.add_to_hass(hass)
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "access_token": "new-access-token",
            "refresh_token": "rotated-refresh-token",
            "expires_in": 7200,
            "token_type": "Bearer",
        },
    )
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    await session.async_ensure_token_valid()

    assert entry.data[CONF_TOKEN]["access_token"] == "new-access-token"
    assert entry.data[CONF_TOKEN]["refresh_token"] == "rotated-refresh-token"
