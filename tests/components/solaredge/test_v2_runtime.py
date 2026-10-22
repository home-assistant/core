"""Synthetic V2 runtime/config-flow regressions; no live provider responses."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from aiosolaredge.v2 import (
    AuthenticationError,
    RateLimitError,
    Reading,
    SolarEdgeV2Error,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator
from yarl import URL

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.components.solaredge.application_credentials import (
    async_get_auth_implementation,
)
from homeassistant.components.solaredge.config_flow import SolarEdgeConfigFlow
from homeassistant.components.solaredge.v2_runtime import (
    SolarEdgeV2Coordinator,
    retry_deadline,
)
from homeassistant.components.solaredge.v2_sensor import (
    ENERGY,
    POWER,
    SolarEdgeV2Sensor,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import (
    config_entry_oauth2_flow as oauth,
    entity_registry as er,
)
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

BASE = "https://monitoringapi.solaredge.com/v2"


def entry_data() -> dict:
    """Return synthetic credentials only."""
    return {
        "site_id": "123",
        "api_version": 2,
        "auth_implementation": "solaredge",
        "token": {
            "access_token": "synthetic",
            "refresh_token": "synthetic-refresh",
            "expires_at": 9999999999,
            "expires_in": 7200,
            "token_type": "Bearer",
        },
    }


def coordinator(hass: HomeAssistant, entry: MockConfigEntry) -> SolarEdgeV2Coordinator:
    """Create the actual scheduler with an isolated OAuth seam."""
    session = Mock()
    session.async_ensure_token_valid = AsyncMock()
    session.token = entry.data["token"]
    return SolarEdgeV2Coordinator(hass, entry, session)


async def test_http_poll_and_reload_cache(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Actual client transport, normalized units and disk cache prevent restart bursts."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    now = dt_util.utcnow()
    aioclient_mock.get(
        BASE + "/sites/123/lifetime-energy",
        json={"energy": 12, "unit": "KWH", "lastUpdateTime": now.isoformat()},
    )
    aioclient_mock.get(
        BASE + "/sites/123/power",
        json={
            "unit": "W",
            "resolution": "QUARTER_HOUR",
            "values": [
                {"timestamp": (now - timedelta(minutes=15)).isoformat(), "value": None}
            ],
        },
    )
    aioclient_mock.get(BASE + "/sites/123", json={"siteId": 123})
    aioclient_mock.get(BASE + "/sites/123/devices", json=[])
    coord = coordinator(hass, entry)
    assert coord.update_interval == timedelta(hours=1)
    await coord._async_setup()
    data = await coord._async_update_data()
    assert data["lifetime_energy"].value == 12000
    assert data["average_power"].value is None
    assert aioclient_mock.call_count == 4
    assert len(coord.state["calls"]) == 8
    coord2 = coordinator(hass, entry)
    await coord2._async_setup()
    assert await coord2._async_update_data() == data
    assert aioclient_mock.call_count == 4
    assert coord2.state["next_poll"] == coord.state["next_poll"]


@pytest.mark.parametrize(
    ("error", "hours"),
    [
        # These fixtures model transport HTTP 429, not a local reservation refusal.
        (RateLimitError("30", http_status=429), 1),
        (RateLimitError(None, http_status=429), 768),
        (RateLimitError("7200", http_status=429), 2),
        (SolarEdgeV2Error(), 1),
    ],
)
async def test_backoff_persists(
    hass: HomeAssistant, error: Exception, hours: int
) -> None:
    """CPM, unknown/monthly exhaustion and outages never form retry loops."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    coord = coordinator(hass, entry)
    coord.api = Mock(lifetime_energy=AsyncMock(side_effect=error), power=AsyncMock())
    now = dt_util.utcnow()
    with patch(
        "homeassistant.components.solaredge.v2_runtime.dt_util.utcnow", return_value=now
    ):
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()
        assert coord.state["next_poll"] == (now + timedelta(hours=hours)).timestamp()
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()
    coord.api.lifetime_energy.assert_awaited_once()
    coord.api.power.assert_not_awaited()
    restored = coordinator(hass, entry)
    await restored._async_setup()
    with pytest.raises(UpdateFailed):
        await restored._async_update_data()
    assert restored.state["failed"] is True


async def test_budget_and_auth(hass: HomeAssistant) -> None:
    """Reserve limits include failed requests; 401 asks for controlled reauthorization."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    coord = coordinator(hass, entry)
    coord.api = Mock(
        lifetime_energy=AsyncMock(side_effect=AuthenticationError()), power=AsyncMock()
    )
    with pytest.raises(ConfigEntryAuthFailed):
        await coord._async_update_data()
    assert len(coord.state["calls"]) == 8
    coord.state.update(calls=[dt_util.utcnow().timestamp()] * 1500, next_poll=0)
    with pytest.raises(UpdateFailed, match="reserve exhausted"):
        await coord._async_update_data()
    coord.api.lifetime_energy.assert_awaited_once()


async def test_unavailable_recovery_and_identity(hass: HomeAssistant) -> None:
    """Preserve lifetime unique ID/state class; instantaneous entity is never repurposed."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    coord = coordinator(hass, entry)
    coord.async_set_updated_data(
        {
            "lifetime_energy": Reading(42, dt_util.utcnow()),
            "average_power": Reading(0, dt_util.utcnow()),
        }
    )
    energy = SolarEdgeV2Sensor(coord, ENERGY)
    power = SolarEdgeV2Sensor(coord, POWER)
    unsupported = SolarEdgeV2Sensor(coord, POWER, unsupported=True)
    assert energy.unique_id == "123_lifetime_energy"
    assert power.unique_id == "123_average_power"
    assert energy.native_value == 42
    assert power.native_value == 0
    assert unsupported.available is False
    coord.async_set_update_error(UpdateFailed("synthetic outage"))
    assert energy.available is False
    coord.async_set_updated_data(coord.data)
    assert energy.available is True


@pytest.mark.usefixtures("recorder_mock", "mock_setup_entry")
@pytest.mark.parametrize("source", [SOURCE_USER, SOURCE_RECONFIGURE, SOURCE_REAUTH])
async def test_native_oauth_flow(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    source: str,
    hass_client: ClientSessionGenerator,
) -> None:
    """Real HA flow and signed authorize URI; same entry survives migration/reauth."""
    hass.config.external_url = "https://ha.example.com"
    implementation = await async_get_auth_implementation(
        hass, "solaredge", ClientCredential("synthetic-client", "synthetic-secret")
    )
    oauth.async_register_implementation(hass, "solaredge", implementation)
    old = MockConfigEntry(
        domain="solaredge",
        title="Synthetic title",
        unique_id="synthetic-identity",
        data={
            "site_id": "123",
            "api_key": "synthetic-old",
            "username": "synthetic-web",
            "password": "synthetic-password",
        },
    )
    context = {"source": source}
    if source != SOURCE_USER:
        old.add_to_hass(hass)
        context["entry_id"] = old.entry_id
    initial = await hass.config_entries.flow.async_init(
        "solaredge", context=context, data=old.data if source == SOURCE_REAUTH else None
    )
    assert initial["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        initial["flow_id"],
        {}
        if source == SOURCE_REAUTH
        else (
            {"site_id": "123", "use_oauth": True}
            if source == SOURCE_USER
            else {"use_oauth": True}
        ),
    )
    assert result["step_id"] == "pick_implementation"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"implementation": "solaredge"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    url = URL(result["url"])
    assert url.query["state"] == url.query["external_id"]
    assert (
        url.query["redirect_uri"]
        == "https://ha.example.com/auth/external/callback/solaredge"
    )
    aioclient_mock.post(
        BASE + "/oauth2/token",
        json={
            "access_token": "synthetic-new",
            "refresh_token": "synthetic-rotation",
            "expires_in": 7200,
            "token_type": "Bearer",
        },
    )
    aioclient_mock.get(BASE + "/sites/123", json={"siteId": 123})
    client = await hass_client()
    response = await client.get(
        "/auth/external/callback/solaredge",
        params={
            "code": "synthetic-code",
            "external_id": url.query["external_id"],
            "site_id": "untrusted-999",
        },
    )
    assert response.status == 200
    body = await response.text()
    assert "Return to Home Assistant" in body
    assert "synthetic-code" not in body
    assert url.query["external_id"] not in body
    assert response.headers["Cache-Control"] == "no-store"
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    if source == SOURCE_USER:
        assert result["type"] is FlowResultType.CREATE_ENTRY
        entry = result["result"]
    else:
        assert result["type"] is FlowResultType.ABORT
        entry = old
        assert entry.unique_id == "synthetic-identity"
        assert entry.title == "Synthetic title"
        assert entry.data["username"] == "synthetic-web"
        assert "api_key" not in entry.data
    assert entry.data["api_version"] == 2
    assert entry.data["site_id"] == "123"
    assert entry.data["token"]["refresh_token"] == "synthetic-rotation"


@pytest.mark.usefixtures("recorder_mock")
async def test_runtime_setup_keeps_registry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
) -> None:
    """Actual platform setup/unload keeps entity IDs and old instantaneous placeholder."""
    entry = MockConfigEntry(domain="solaredge", title="SolarEdge", data=entry_data())
    entry.add_to_hass(hass)
    registry = entity_registry
    old = registry.async_get_or_create(
        "sensor",
        "solaredge",
        "123_lifetime_energy",
        suggested_object_id="solaredge_lifetime_energy",
        config_entry=entry,
    )
    instantaneous = registry.async_get_or_create(
        "sensor",
        "solaredge",
        "123_current_power",
        suggested_object_id="solaredge_current_power",
        config_entry=entry,
    )
    impl = await async_get_auth_implementation(
        hass, "solaredge", ClientCredential("synthetic", "synthetic")
    )
    oauth.async_register_implementation(hass, "solaredge", impl)
    now = dt_util.utcnow()
    aioclient_mock.get(
        BASE + "/sites/123/lifetime-energy",
        json={"energy": 1234, "unit": "WH", "lastUpdateTime": now.isoformat()},
    )
    aioclient_mock.get(
        BASE + "/sites/123/power",
        json={
            "unit": "W",
            "resolution": "QUARTER_HOUR",
            "values": [
                {"timestamp": (now - timedelta(minutes=15)).isoformat(), "value": 25}
            ],
        },
    )
    aioclient_mock.get(BASE + "/sites/123", json={"siteId": 123})
    aioclient_mock.get(BASE + "/sites/123/devices", json=[])
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(old.entity_id).state == "1234.0"
    assert hass.states.get(instantaneous.entity_id).state == "unavailable"
    assert registry.async_get(old.entity_id).unique_id == "123_lifetime_energy"
    assert aioclient_mock.call_count == 4
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 4
    assert hass.states.get(old.entity_id).state == "1234.0"


def test_retry_http_date() -> None:
    """Respect HTTP dates, not just seconds, for provider quota deadlines."""
    now = dt_util.utcnow()
    assert retry_deadline("garbage", now) == now + timedelta(days=32)
    assert retry_deadline("Wed, 21 Oct 2037 12:00:00 GMT", now).year == 2037
    assert retry_deadline("3456000", now) == now + timedelta(days=40)


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize("site_id", ["../123", "１２３", "123?token=bad", ""])
async def test_site_id_rejected_before_oauth(hass: HomeAssistant, site_id: str) -> None:
    """Never build provider requests from malformed untrusted site IDs."""
    initial = await hass.config_entries.flow.async_init(
        "solaredge", context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        initial["flow_id"], {"site_id": site_id, "use_oauth": True}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_site"


async def test_authorized_site_mismatch(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A successful HTTP request alone does not authorize a different site's binding."""
    flow = SolarEdgeConfigFlow()
    flow.hass = hass
    flow._oauth_site_id = "123"
    flow.context = {"source": SOURCE_USER}
    aioclient_mock.get(BASE + "/sites/123", json={"siteId": 999})
    result = await flow.async_oauth_create_entry(entry_data())
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_site"
    assert hass.config_entries.async_entries("solaredge") == []


async def test_outage_exponential_recovery(hass: HomeAssistant) -> None:
    """Outage attempts are bounded, never zero values, then resume real readings."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    coord = coordinator(hass, entry)
    coord.api = Mock(
        lifetime_energy=AsyncMock(side_effect=SolarEdgeV2Error()), power=AsyncMock()
    )
    now = dt_util.utcnow()
    for hours in (1, 2, 4, 8, 16, 24):
        with (
            patch(
                "homeassistant.components.solaredge.v2_runtime.dt_util.utcnow",
                return_value=now,
            ),
            pytest.raises(UpdateFailed),
        ):
            await coord._async_update_data()
        assert coord.state["next_poll"] == (now + timedelta(hours=hours)).timestamp()
        now += timedelta(hours=hours)
    coord.api.lifetime_energy = AsyncMock(return_value=Reading(17, now))
    coord.api.power = AsyncMock(return_value=Reading(0, now))
    coord.api.site = AsyncMock(return_value={"siteId": 123})
    coord.api.inventory = AsyncMock(return_value={"batteries": []})
    with patch(
        "homeassistant.components.solaredge.v2_runtime.dt_util.utcnow", return_value=now
    ):
        result = await coord._async_update_data()
    assert result["lifetime_energy"].value == 17
    assert result["average_power"].value == 0
    assert coord.state["failures"] == 0
    assert coord.state["failed"] is False
