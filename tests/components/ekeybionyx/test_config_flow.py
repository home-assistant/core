"""Test the Ekey Bionyx config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.ekeybionyx.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    SCOPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from .conftest import dummy_systems

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    "ignore_missing_translations",
    [
        [
            "component.ekeybionyx.config.step.webhooks.data_description.webhook1",
            "component.ekeybionyx.config.step.webhooks.data_description.webhook2",
            "component.ekeybionyx.config.step.webhooks.data_description.webhook3",
            "component.ekeybionyx.config.step.webhooks.data_description.webhook4",
            "component.ekeybionyx.config.step.webhooks.data_description.webhook5",
        ]
    ],
)
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
    webhook_id: None,
    system: None,
    token_hex: None,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        f"&scope={SCOPE}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )
    flow = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert flow.get("step_id") == "choose_system"

    flow2 = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"system": "946DA01F-9ABD-4D9D-80C7-02AF85C822A8"}
    )
    assert flow2.get("step_id") == "webhooks"

    flow3 = await hass.config_entries.flow.async_configure(
        flow2["flow_id"],
        {
            "url": "localhost:8123",
        },
    )

    assert flow3.get("errors") == {"base": "no_webhooks_provided", "url": "invalid_url"}

    flow4 = await hass.config_entries.flow.async_configure(
        flow3["flow_id"],
        {
            "webhook1": "Test ",
            "webhook2": " Invalid",
            "webhook3": "1Invalid",
            "webhook4": "Also@Invalid",
            "webhook5": "Invalid-Name",
            "url": "localhost:8123",
        },
    )

    assert flow4.get("errors") == {
        "url": "invalid_url",
        "webhook1": "invalid_name",
        "webhook2": "invalid_name",
        "webhook3": "invalid_name",
        "webhook4": "invalid_name",
        "webhook5": "invalid_name",
    }

    with patch(
        "homeassistant.components.ekeybionyx.async_setup_entry", return_value=True
    ) as mock_setup:
        flow5 = await hass.config_entries.flow.async_configure(
            flow2["flow_id"],
            {
                "webhook1": "Test",
                "url": "http://localhost:8123",
            },
        )
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert hass.config_entries.async_entries(DOMAIN)[0].data == {
        "webhooks": [
            {
                "webhook_id": "1234567890",
                "name": "Test",
                "auth": "f2156edca7fc6871e13845314a6fc68622e5ad7c58f17663a487ed28cac247f7",
                "ekey_id": "946DA01F-9ABD-4D9D-80C7-02AF85C822A8",
            }
        ]
    }

    assert flow5.get("type") is FlowResultType.CREATE_ENTRY

    assert len(mock_setup.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
async def test_no_own_system(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
    no_own_system: None,
) -> None:
    """Check no own System flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        f"&scope={SCOPE}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )
    flow = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 0

    assert flow.get("type") is FlowResultType.ABORT
    assert flow.get("reason") == "no_own_systems"


@pytest.mark.usefixtures("current_request_with_host")
async def test_no_available_webhooks(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
    no_available_webhooks: None,
) -> None:
    """Check no own System flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        f"&scope={SCOPE}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )
    flow = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 0

    assert flow.get("type") is FlowResultType.ABORT
    assert flow.get("reason") == "no_available_webhooks"


@pytest.mark.usefixtures("current_request_with_host")
async def test_cleanup(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
    already_set_up: None,
    webhooks: None,
    webhook_deletion: None,
) -> None:
    """Check no own System flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        f"&scope={SCOPE}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    flow = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert flow.get("step_id") == "delete_webhooks"

    flow2 = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    assert flow2.get("type") is FlowResultType.SHOW_PROGRESS

    aioclient_mock.clear_requests()

    aioclient_mock.get(
        "https://api.bionyx.io/3rd-party/api/systems",
        json=dummy_systems(1, 1, 0),
    )

    await hass.async_block_till_done()

    assert (
        hass.config_entries.flow.async_get(flow2["flow_id"]).get("step_id")
        == "webhooks"
    )


@pytest.mark.usefixtures("current_request_with_host")
async def test_error_on_setup(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
    no_response: None,
) -> None:
    """Check no own System flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        f"&scope={SCOPE}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )
    flow = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 0

    assert flow.get("type") is FlowResultType.ABORT
    assert flow.get("reason") == "cannot_connect"
