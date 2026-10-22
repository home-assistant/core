"""Native lifecycle and credential-intent regressions; all HTTP is synthetic."""

import asyncio
import copy
from unittest.mock import AsyncMock, patch

from aiosolaredge.v2 import RateLimitError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator
from yarl import URL

from homeassistant.components import http
from homeassistant.components.application_credentials import (
    DATA_COMPONENT,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.solaredge.application_credentials import (
    async_get_auth_implementation,
)
from homeassistant.components.solaredge.coordinator import SolarEdgeV2Coordinator
from homeassistant.components.solaredge.v2_budget import SolarEdgeBudget, get_budget
from homeassistant.components.solaredge.v2_runtime import async_repair_authorization
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_entry_oauth2_flow as oauth
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .test_community import register_basic
from .test_oauth_callback import start_flow
from .test_v2_runtime import coordinator, entry_data


@pytest.mark.usefixtures("recorder_mock")
async def test_saved_credential_appearing_while_form_open(hass: HomeAssistant) -> None:
    """Test saved credential appearing while form open."""
    assert await async_setup_component(hass, "application_credentials", {})
    hass.config.external_url = "https://ha.example.com"
    result = await hass.config_entries.flow.async_init(
        "solaredge", context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"site_id": "123", "use_oauth": True}
    )
    assert result["step_id"] == "oauth_application"
    await async_import_client_credential(
        hass,
        "solaredge",
        ClientCredential("older-app", "older-secret"),
        auth_domain="solaredge_older_app",
    )
    request_context = http.current_request.set(object())
    try:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"client_id": "requested-new-app", "client_secret": "requested-new-secret"},
        )
    finally:
        http.current_request.reset(request_context)
    assert len(hass.data[DATA_COMPONENT].async_items()) == 2
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert URL(result["url"]).query["client_id"] == "requested-new-app"


@pytest.mark.usefixtures("recorder_mock")
async def test_successful_native_reauth_repairs_auth_failure_pause(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test successful native reauth repairs auth failure pause."""
    hass.config.external_url = "https://ha.example.com"
    impl = await async_get_auth_implementation(
        hass, "solaredge", ClientCredential("synthetic", "synthetic")
    )
    oauth.async_register_implementation(hass, "solaredge", impl)
    entry = MockConfigEntry(domain="solaredge", title="Preserved", data=entry_data())
    entry.add_to_hass(hass)
    old = SolarEdgeV2Coordinator(hass, entry, oauth.OAuth2Session(hass, entry, impl))
    now = dt_util.utcnow()
    aioclient_mock.get(
        "https://monitoringapi.solaredge.com/v2/sites/123/lifetime-energy", status=401
    )
    with pytest.raises(ConfigEntryAuthFailed):
        await old._async_update_data()
    assert old.state["failed"] is True
    assert old.state["next_poll"] > now.timestamp() + 7000
    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"implementation": "solaredge"}
    )
    query = URL(result["url"]).query
    aioclient_mock.post(
        "https://monitoringapi.solaredge.com/v2/oauth2/token",
        json={
            "access_token": "new-valid",
            "refresh_token": "new-rotation",
            "token_type": "Bearer",
            "expires_in": 7200,
        },
    )
    aioclient_mock.get(
        "https://monitoringapi.solaredge.com/v2/sites/123",
        json={"siteId": 123, "location": {"timezone": "Europe/Amsterdam"}},
    )
    client = await hass_client()
    response = await client.get(
        "/auth/external/callback/solaredge",
        params={"external_id": query["external_id"], "code": "synthetic-code"},
    )
    assert response.status == 200
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload",
        new=AsyncMock(return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["reason"] == "reauth_successful"
        await hass.async_block_till_done()
    assert entry.data["token"]["refresh_token"] == "new-rotation"
    restored = SolarEdgeV2Coordinator(
        hass, entry, oauth.OAuth2Session(hass, entry, impl)
    )
    await restored._async_setup()
    aioclient_mock.clear_requests()
    register_basic(aioclient_mock, now)
    entry._async_set_state(hass, ConfigEntryState.SETUP_IN_PROGRESS, None)
    await restored.async_config_entry_first_refresh()
    assert restored.last_update_success
    assert restored.data["lifetime_energy"].value == 12000
    assert aioclient_mock.call_count == 7
    assert len(restored.budget.state["calls"]) == 10
    assert len(restored.state["calls"]) == 15
    assert entry.title == "Preserved"
    assert entry.data["site_id"] == "123"
    assert restored.state["failed"] is False


async def test_actual_json_refresh_is_serialized_and_rotated(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test actual json refresh is serialized and rotated."""
    impl = await async_get_auth_implementation(
        hass, "solaredge", ClientCredential("synthetic", "synthetic")
    )
    data = entry_data()
    data["token"]["expires_at"] = 0
    entry = MockConfigEntry(domain="solaredge", data=data)
    entry.add_to_hass(hass)
    session = oauth.OAuth2Session(hass, entry, impl)
    aioclient_mock.post(
        "https://monitoringapi.solaredge.com/v2/oauth2/token",
        json={
            "access_token": "synthetic-new",
            "refresh_token": "synthetic-rotated",
            "expires_in": 7200,
            "token_type": "Bearer",
        },
    )
    await asyncio.gather(*(session.async_ensure_token_valid() for _ in range(8)))
    assert aioclient_mock.call_count == 1
    assert entry.data["token"]["refresh_token"] == "synthetic-rotated"
    assert len(get_budget(hass).state["calls"]) == 1
    assert aioclient_mock.mock_calls[0][2]["refresh_token"] == "synthetic-refresh"


async def test_actual_refresh_429_does_not_reauth_and_persists_pause(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test actual refresh 429 does not reauth and persists pause."""
    impl = await async_get_auth_implementation(
        hass, "solaredge", ClientCredential("synthetic", "synthetic")
    )
    data = entry_data()
    data["token"]["expires_at"] = 0
    entry = MockConfigEntry(domain="solaredge", data=data)
    entry.add_to_hass(hass)
    coord = SolarEdgeV2Coordinator(hass, entry, oauth.OAuth2Session(hass, entry, impl))
    aioclient_mock.post(
        "https://monitoringapi.solaredge.com/v2/oauth2/token",
        status=429,
        headers={"Retry-After": "7200"},
        text="synthetic-secret-do-not-log",
    )
    with patch.object(entry, "async_start_reauth_if_available") as reauth:
        with pytest.raises(UpdateFailed, match="polling backed off"):
            await coord._async_update_data()
        reauth.assert_not_called()
    assert aioclient_mock.call_count == 1
    restored = SolarEdgeBudget(hass)
    with pytest.raises(RateLimitError):
        await restored.reserve()
    assert restored.state["blocked"] > dt_util.utcnow().timestamp() + 7000
    assert entry.data["token"]["refresh_token"] == "synthetic-refresh"


@pytest.mark.usefixtures("recorder_mock")
async def test_provider_error_callback_is_redacted_and_single_use(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test provider error callback is redacted and single use."""
    flow_id, encoded = await start_flow(hass)
    client = await hass_client()
    params = {"external_id": encoded, "error": "synthetic-secret-provider-echo"}
    response = await client.get("/auth/external/callback/solaredge", params=params)
    assert response.status == 200
    assert "synthetic-secret-provider-echo" not in await response.text()
    assert (
        await client.get("/auth/external/callback/solaredge", params=params)
    ).status == 400
    assert aioclient_mock.call_count == 0
    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["reason"] == "user_rejected_authorize"
    assert result["description_placeholders"]["error"] == "access_denied"


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    ("submitted", "expected_error"),
    [
        ({"client_id": "same-app", "client_secret": "same-secret"}, None),
        (
            {"client_id": "same-app", "client_secret": "different"},
            "oauth_credentials_conflict",
        ),
        ({"client_id": "new-app"}, "oauth_credentials_required"),
    ],
)
async def test_two_open_forms_reconcile_intent(
    hass: HomeAssistant, submitted: dict[str, str], expected_error: str | None
) -> None:
    """Test two open forms reconcile intent."""
    assert await async_setup_component(hass, "application_credentials", {})
    hass.config.external_url = "https://ha.example.com"
    flows = []
    for _ in range(2):
        result = await hass.config_entries.flow.async_init(
            "solaredge", context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"site_id": "123", "use_oauth": True}
        )
        assert result["step_id"] == "oauth_application"
        flows.append(result["flow_id"])
    pair = {"client_id": "same-app", "client_secret": "same-secret"}
    result = await hass.config_entries.flow.async_configure(flows[0], pair)
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    result = await hass.config_entries.flow.async_configure(flows[1], submitted)
    if expected_error:
        assert result["step_id"] == "oauth_application"
        assert result["errors"] == {"base": expected_error}
    else:
        assert URL(result["url"]).query["client_id"] == "same-app"
    saved = hass.data[DATA_COMPONENT].async_items()
    assert len(saved) == 1
    assert saved[0]["client_secret"] == "same-secret"


@pytest.mark.parametrize("cause", ["quota", "timeout", "monthly"])
async def test_authorization_repair_preserves_non_auth_pause(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, cause: str
) -> None:
    """Test authorization repair preserves non auth pause."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    coord = coordinator(hass, entry)
    coord.state["auth_failed_jobs"] = ["lifetime"]
    if cause == "quota":
        aioclient_mock.get(
            "https://monitoringapi.solaredge.com/v2/sites/123/lifetime-energy",
            status=429,
            headers={"Retry-After": "7200"},
        )
    elif cause == "timeout":
        aioclient_mock.get(
            "https://monitoringapi.solaredge.com/v2/sites/123/lifetime-energy",
            exc=TimeoutError(),
        )
    else:
        coord.state["calls"] = [dt_util.utcnow().timestamp()] * 1500
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()
    before = copy.deepcopy(coord.state)
    budget_before = copy.deepcopy(coord.budget.state)
    await async_repair_authorization(hass, entry.entry_id, {"timezone": "UTC"})
    restored = coordinator(hass, entry)
    await restored._async_setup()
    assert restored.state == before
    assert coord.budget.state == budget_before
