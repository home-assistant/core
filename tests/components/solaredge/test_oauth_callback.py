"""Native SolarEdge callback security regressions; all values are synthetic."""

import asyncio
import time

import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator
from yarl import URL

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.components.solaredge.application_credentials import (
    async_get_auth_implementation,
)
from homeassistant.components.solaredge.oauth_callback import (
    CALLBACK_PATH,
    DATA_PENDING,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow as oauth


async def start_flow(hass: HomeAssistant) -> tuple[str, str]:
    """Start the real flow and obtain its generated, signed correlation value."""
    hass.config.external_url = "https://example.com"
    impl = await async_get_auth_implementation(
        hass, "synthetic-app", ClientCredential("synthetic-client", "synthetic-secret")
    )
    oauth.async_register_implementation(hass, "solaredge", impl)
    result = await hass.config_entries.flow.async_init(
        "solaredge", context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_oauth": True, "site_id": "123"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"implementation": "synthetic-app"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    query = URL(result["url"]).query
    assert query["state"] == query["external_id"]
    assert oauth._decode_jwt(hass, query["state"])["flow_id"] == result["flow_id"]
    return result["flow_id"], query["state"]


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "bare-site",
        "static-id",
        "tampered",
        "mismatch",
        "duplicate",
        "missing-code",
        "code-and-error",
        "expired",
        "wrong-flow",
        "wrong-domain",
        "wrong-implementation",
        "wrong-redirect",
        "wrong-site-binding",
        "inactive",
        "not-auth",
    ],
)
async def test_invalid_callback(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    case: str,
) -> None:
    """No unbound callback may resume consent or initiate token exchange."""
    flow_id, encoded = await start_flow(hass)
    client = await hass_client()
    attempt = hass.data[DATA_PENDING][encoded]
    params = {
        "external_id": encoded,
        "code": "synthetic-evil-code",
        "site_id": "untrusted-999",
    }
    match case:
        case "missing":
            del params["external_id"]
        case "bare-site":
            params = {"code": "synthetic-evil-code", "site_id": "123"}
        case "static-id":
            params["external_id"] = "synthetic-static-customer"
        case "tampered":
            params["external_id"] += "tampered"
        case "mismatch":
            params["state"] = "synthetic-other-state"
        case "duplicate":
            params = [*params.items(), ("external_id", encoded)]
        case "missing-code":
            del params["code"]
        case "code-and-error":
            params["error"] = "synthetic-error"
        case "expired":
            attempt.expires = time.time() - 1
        case "wrong-flow":
            attempt.flow.flow_id = "synthetic-other-flow"
        case "wrong-domain":
            attempt.flow.DOMAIN = "synthetic-other-provider"
        case "wrong-implementation":
            attempt.flow.flow_impl = await async_get_auth_implementation(
                hass,
                "synthetic-other-app",
                ClientCredential("synthetic-other", "synthetic-secret"),
            )
        case "wrong-redirect":
            attempt.redirect_uri = "https://evil.invalid/callback"
        case "wrong-site-binding":
            attempt.flow._oauth_site_id = "999"
        case "inactive":
            hass.config_entries.flow.async_abort(flow_id)
        case "not-auth":
            attempt.flow.cur_step = {
                "type": FlowResultType.EXTERNAL_STEP_DONE,
                "step_id": "creation",
            }
    response = await client.get(CALLBACK_PATH, params=params)
    assert response.status == 400
    assert await response.text() == "Invalid SolarEdge OAuth callback"
    assert aioclient_mock.call_count == 0


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize("carrier", ["state", "external_id"])
async def test_one_use_native_callback(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    carrier: str,
) -> None:
    """Standard state and provider-only external_id share the same one-use gate."""
    flow_id, encoded = await start_flow(hass)
    client = await hass_client()
    params = {carrier: encoded, "code": "synthetic-code", "site_id": "untrusted-999"}
    responses = await asyncio.gather(
        client.get(CALLBACK_PATH, params=params),
        client.get(CALLBACK_PATH, params=params),
    )
    assert sorted(response.status for response in responses) == [200, 400]
    assert hass.config_entries.flow.async_get(flow_id)["step_id"] == "creation"
    assert encoded not in hass.data[DATA_PENDING]
    assert aioclient_mock.call_count == 0


@pytest.mark.usefixtures("recorder_mock")
async def test_generic_callback_cannot_bypass_adapter(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The unchanged generic callback cannot bypass SolarEdge's pending checks."""
    flow_id, encoded = await start_flow(hass)
    hass.http.register_view(oauth.OAuth2AuthorizeCallbackView)
    client = await hass_client()
    response = await client.get(
        oauth.AUTH_CALLBACK_PATH, params={"state": encoded, "code": "synthetic-code"}
    )
    assert response.status == 200
    assert aioclient_mock.call_count == 0
    assert (
        hass.config_entries.flow.async_get(flow_id)["step_id"] == "authorize_rejected"
    )
    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["type"] is FlowResultType.ABORT


@pytest.mark.usefixtures("recorder_mock")
async def test_signed_expiry_rejected(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A registered state with an expired HA MAC-authenticated exp is rejected."""
    _, original = await start_flow(hass)
    claims = oauth._decode_jwt(hass, original)
    encoded = oauth._encode_jwt(hass, {**claims, "exp": int(time.time()) - 60})
    hass.data[DATA_PENDING][encoded] = hass.data[DATA_PENDING].pop(original)
    client = await hass_client()
    response = await client.get(
        CALLBACK_PATH, params={"external_id": encoded, "code": "synthetic-code"}
    )
    assert response.status == 400
    assert aioclient_mock.call_count == 0
