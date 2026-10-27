"""Tests for the SolarEdge V2 API client."""

import time

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.solaredge.api import SolarEdgeRateLimitError, SolarEdgeV2
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
        repeat=True,
    )
    aioclient_mock.get(
        f"{API_BASE_URL}/sites/{SITE_ID}/energy",
        json={"unit": "KWH", "values": [{"value": 12.0}]},
        repeat=True,
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
    assert exc_info.value.retry_after is None


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
        ],
    )
    api = SolarEdgeV2(async_get_clientsession(hass), async_access_token)

    result = await api.get_inventory(SITE_ID)

    assert result["Inventory"]["inverters"][0]["SN"] == "inverter-1"
    assert result["Inventory"]["batteries"][0]["SN"] == "battery-1"


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
                            {"timestamp": "2026-10-21T12:00:00Z", "value": 2500}
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
