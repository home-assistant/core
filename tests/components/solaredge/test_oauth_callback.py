"""Native SolarEdge callback security regressions; all values are synthetic."""

import asyncio
from collections.abc import Awaitable, Callable
import time
from typing import Any

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


CODE = "synthetic-evil-code"
SITE = "untrusted-999"


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    "build_params",
    [
        pytest.param(lambda state: {"code": CODE, "site_id": SITE}, id="missing"),
        pytest.param(lambda state: {"code": CODE, "site_id": "123"}, id="bare-site"),
        pytest.param(
            lambda state: {
                "external_id": "synthetic-static-customer",
                "code": CODE,
                "site_id": SITE,
            },
            id="static-id",
        ),
        pytest.param(
            lambda state: {"external_id": state + "tampered", "code": CODE},
            id="tampered",
        ),
        pytest.param(
            lambda state: {
                "external_id": state,
                "state": "synthetic-other-state",
                "code": CODE,
            },
            id="mismatch",
        ),
        pytest.param(
            lambda state: [
                ("external_id", state),
                ("code", CODE),
                ("external_id", state),
            ],
            id="duplicate",
        ),
        pytest.param(
            lambda state: {"external_id": state, "site_id": SITE}, id="missing-code"
        ),
        pytest.param(
            lambda state: {
                "external_id": state,
                "code": CODE,
                "error": "synthetic-error",
            },
            id="code-and-error",
        ),
    ],
)
async def test_invalid_callback_query(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    build_params: Callable[[str], dict[str, str] | list[tuple[str, str]]],
) -> None:
    """No malformed or unbound carrier may resume consent or exchange a code."""
    _, encoded = await start_flow(hass)
    client = await hass_client()
    response = await client.get(CALLBACK_PATH, params=build_params(encoded))
    assert response.status == 400
    assert await response.text() == "Invalid SolarEdge OAuth callback"
    assert aioclient_mock.call_count == 0


async def _expire(hass: HomeAssistant, flow_id: str, attempt: Any) -> None:
    attempt.expires = time.time() - 1


async def _other_flow(hass: HomeAssistant, flow_id: str, attempt: Any) -> None:
    attempt.flow.flow_id = "synthetic-other-flow"


async def _other_domain(hass: HomeAssistant, flow_id: str, attempt: Any) -> None:
    attempt.flow.DOMAIN = "synthetic-other-provider"


async def _other_implementation(
    hass: HomeAssistant, flow_id: str, attempt: Any
) -> None:
    attempt.flow.flow_impl = await async_get_auth_implementation(
        hass,
        "synthetic-other-app",
        ClientCredential("synthetic-other", "synthetic-secret"),
    )


async def _other_redirect(hass: HomeAssistant, flow_id: str, attempt: Any) -> None:
    attempt.redirect_uri = "https://evil.invalid/callback"


async def _other_site(hass: HomeAssistant, flow_id: str, attempt: Any) -> None:
    attempt.flow._oauth_site_id = "999"


async def _inactive(hass: HomeAssistant, flow_id: str, attempt: Any) -> None:
    hass.config_entries.flow.async_abort(flow_id)


async def _not_auth(hass: HomeAssistant, flow_id: str, attempt: Any) -> None:
    attempt.flow.cur_step = {
        "type": FlowResultType.EXTERNAL_STEP_DONE,
        "step_id": "creation",
    }


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    "tamper",
    [
        pytest.param(_expire, id="expired"),
        pytest.param(_other_flow, id="wrong-flow"),
        pytest.param(_other_domain, id="wrong-domain"),
        pytest.param(_other_implementation, id="wrong-implementation"),
        pytest.param(_other_redirect, id="wrong-redirect"),
        pytest.param(_other_site, id="wrong-site-binding"),
        pytest.param(_inactive, id="inactive"),
        pytest.param(_not_auth, id="not-auth"),
    ],
)
async def test_invalid_callback_binding(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    tamper: Callable[[HomeAssistant, str, Any], Awaitable[None]],
) -> None:
    """A valid carrier is rejected once its pending flow binding changed."""
    flow_id, encoded = await start_flow(hass)
    client = await hass_client()
    await tamper(hass, flow_id, hass.data[DATA_PENDING][encoded])
    response = await client.get(
        CALLBACK_PATH, params={"external_id": encoded, "code": CODE, "site_id": SITE}
    )
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
