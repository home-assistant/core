"""Tests for the SmartThings config flow module."""

import asyncio
from http import HTTPStatus
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from pysmartthings import (
    SmartThingsAuthenticationFailedError,
    SmartThingsConnectionError,
    SmartThingsForbiddenError,
    SmartThingsQuotaExceededError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.application_credentials import (
    DATA_COMPONENT as APPLICATION_CREDENTIALS_DATA_COMPONENT,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.smartthings import OLD_DATA
from homeassistant.components.smartthings.app_ledger import (
    STORAGE_KEY,
    SmartThingsAppLedger,
)
from homeassistant.components.smartthings.const import (
    CONF_LOCATION_ID,
    CONF_PAT_TOKEN,
    CONF_SUBSCRIPTION_ID,
    DOMAIN,
    MANAGE_PLANS_URL,
    PAT_TOKEN_URL,
)
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_ID, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

REDIRECT_URI = "https://example.com/auth/external/callback"


@pytest.fixture
def use_cloud(hass: HomeAssistant) -> None:
    """Set up the cloud component."""
    hass.config.components.add("cloud")


@pytest.fixture
async def without_stored_credentials(hass: HomeAssistant) -> None:
    """Remove stored credentials, so the flow prompts for a PAT."""
    credentials = hass.data[APPLICATION_CREDENTIALS_DATA_COMPONENT]
    for item in list(credentials.async_items()):
        await credentials.async_delete_item(item[CONF_ID])


@pytest.fixture
async def with_generic_credential(hass: HomeAssistant, setup_credentials: None) -> None:
    """Import a generic, already-configured application credential."""
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("CLIENT_ID", "CLIENT_SECRET"),
        DOMAIN,
    )


@pytest.mark.usefixtures("current_request_with_host", "with_generic_credential")
async def test_pat_implementation_auto_selects_stored_credential(
    hass: HomeAssistant,
) -> None:
    """Check a stored credential is used automatically, without prompting for a PAT.

    With no cloud implementation available, the top-level picker is skipped
    entirely, and since a credential is already stored, so is the PAT prompt.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        "https://api.smartthings.com/oauth/authorize"
        "?response_type=code&client_id=CLIENT_ID"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=r:devices:*+w:devices:*+x:devices:*+r:hubs:*+"
        "r:locations:*+w:locations:*+x:locations:*+r:scenes:*+"
        "x:scenes:*+r:rules:*+w:rules:*+sse+r:installedapps:*+"
        "w:installedapps:*"
    )


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@pytest.mark.parametrize(
    ("error", "reason", "placeholders"),
    [
        pytest.param(
            SmartThingsQuotaExceededError("Quota exceeded"),
            "quota_exceeded",
            {"manage_plans_url": MANAGE_PLANS_URL},
            id="quota_exceeded",
        ),
        pytest.param(
            SmartThingsForbiddenError("Forbidden"),
            "entitlement_required",
            None,
            id="forbidden",
        ),
    ],
)
async def test_stored_credential_location_fetch_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    error: Exception,
    reason: str,
    placeholders: dict[str, str] | None,
) -> None:
    """Check a failed location fetch after OAuth aborts with guidance."""
    mock_smartthings.get_locations.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert "client_id=CLIENT_ID" in result["url"]

    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
            "access_tier": 0,
            "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert result["description_placeholders"] == placeholders


@pytest.mark.usefixtures("current_request_with_host")
async def test_pat_flow_records_app_before_storing_credential(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_smartthings: AsyncMock,
) -> None:
    """Check a created app is tracked even if storing its credential fails."""
    mock_smartthings.list_apps.return_value = []

    with patch(
        "homeassistant.components.smartthings.config_flow.async_get_implementations",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "pat"

        with (
            patch.object(
                SmartThingsAppLedger,
                "async_replace_credential",
                side_effect=HomeAssistantError,
            ),
            pytest.raises(HomeAssistantError),
        ):
            await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_PAT_TOKEN: "pat-token"}
            )

    assert hass_storage[STORAGE_KEY]["data"]["apps"] == {"mock-app-id": REDIRECT_URI}


@pytest.mark.usefixtures("current_request_with_host", "without_stored_credentials")
@pytest.mark.parametrize(
    ("ledger_apps", "expected_app_id", "expected_client_id"),
    [
        pytest.param(
            {"existing-app-id": REDIRECT_URI},
            "existing-app-id",
            "regenerated-client-id",
            id="owned_app_reused",
        ),
        pytest.param(
            {},
            "mock-app-id",
            "mock-client-id",
            id="app_of_other_instance_not_reused",
        ),
        pytest.param(
            {"existing-app-id": "https://old.example.com/auth/external/callback"},
            "mock-app-id",
            "mock-client-id",
            id="redirect_uri_changed",
        ),
    ],
)
async def test_pat_flow_only_reuses_owned_app(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_smartthings: AsyncMock,
    ledger_apps: dict[str, str],
    expected_app_id: str,
    expected_client_id: str,
) -> None:
    """Check an existing app is only reused if this instance provisioned it."""
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 2,
        "key": STORAGE_KEY,
        "data": {"apps": ledger_apps},
    }
    mock_smartthings.list_apps.return_value = [
        SimpleNamespace(app_id="existing-app-id", app_name="homeassistant.existing")
    ]
    mock_smartthings.regenerate_oauth.return_value = SimpleNamespace(
        client_id="regenerated-client-id",
        client_secret="regenerated-client-secret",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "pat"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PAT_TOKEN: "pat-token"}
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert f"client_id={expected_client_id}" in result["url"]
    assert hass_storage[STORAGE_KEY]["data"]["apps"][expected_app_id] == REDIRECT_URI


@pytest.mark.usefixtures("current_request_with_host", "without_stored_credentials")
async def test_concurrent_pat_flows_share_app(
    hass: HomeAssistant,
    mock_smartthings: AsyncMock,
) -> None:
    """Check concurrent PAT flows share one app without rotating its credentials."""
    apps: list[SimpleNamespace] = []

    async def list_apps() -> list[SimpleNamespace]:
        # Yield, so the other flow can run while this one is provisioning.
        await asyncio.sleep(0)
        return list(apps)

    async def create_app(**kwargs: Any) -> SimpleNamespace:
        apps.append(SimpleNamespace(app_id="mock-app-id", app_name=kwargs["app_name"]))
        return SimpleNamespace(
            app_id="mock-app-id",
            client_id="mock-client-id",
            client_secret="mock-client-secret",
        )

    mock_smartthings.list_apps.side_effect = list_apps
    mock_smartthings.create_app.side_effect = create_app

    flow_ids = []
    for _ in range(2):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["step_id"] == "pat"
        flow_ids.append(result["flow_id"])

    results = await asyncio.gather(
        *(
            hass.config_entries.flow.async_configure(
                flow_id, {CONF_PAT_TOKEN: "pat-token"}
            )
            for flow_id in flow_ids
        )
    )

    for result in results:
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert "client_id=mock-client-id" in result["url"]
    mock_smartthings.create_app.assert_awaited_once()
    mock_smartthings.regenerate_oauth.assert_not_called()


@pytest.mark.usefixtures(
    "current_request_with_host", "without_stored_credentials", "mock_setup_entry"
)
@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        (SmartThingsAuthenticationFailedError("Invalid token"), "invalid_pat"),
        (SmartThingsForbiddenError("Forbidden"), "entitlement_required"),
        (SmartThingsConnectionError("Timeout"), "cannot_connect"),
        (SmartThingsQuotaExceededError("Quota exceeded"), "quota_exceeded"),
    ],
)
async def test_pat_provisioning_error_and_retry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    error: Exception,
    expected_error: str,
) -> None:
    """Check provisioning errors are shown on the PAT form and can be retried."""
    mock_smartthings.list_apps.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "pat"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PAT_TOKEN: "pat-token"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pat"
    assert result["errors"] == {"base": expected_error}
    assert result["description_placeholders"] == {
        "token_url": PAT_TOKEN_URL,
        "manage_plans_url": MANAGE_PLANS_URL,
    }

    mock_smartthings.list_apps.side_effect = None
    mock_smartthings.list_apps.return_value = []

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PAT_TOKEN: "pat-token"}
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert "client_id=mock-client-id" in result["url"]

    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
            "access_tier": 0,
            "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["app_id"] == "mock-app-id"


@pytest.mark.usefixtures("current_request_with_host", "with_generic_credential")
async def test_pick_implementation_only_offers_cloud_and_pat(
    hass: HomeAssistant,
) -> None:
    """Check the top-level picker only offers cloud and a PAT option.

    Stored credentials are surfaced one level down, under the PAT choice.
    """
    mock_implementations = {
        DOMAIN: SimpleNamespace(name="Import from configuration.yaml"),
        "cloud": SimpleNamespace(name="Nabu Casa Cloud"),
    }
    with patch(
        "homeassistant.components.smartthings.config_flow.async_get_implementations",
        return_value=mock_implementations,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pick_implementation"
        implementation_field = next(iter(result["data_schema"].schema))
        assert implementation_field.default() == "pat"
        selector = result["data_schema"].schema[implementation_field]
        assert selector.config["mode"] == "list"
        assert selector.config["translation_key"] == "implementation"
        assert selector.config["options"] == ["cloud", "pat"]


@pytest.mark.usefixtures("current_request_with_host", "use_cloud", "mock_setup_entry")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
) -> None:
    """Check a full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        "https://api.smartthings.com/oauth/authorize"
        "?response_type=code&client_id=CLIENT_ID"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=r:devices:*+w:devices:*+x:devices:*+r:hubs:*+"
        "r:locations:*+w:locations:*+x:locations:*+r:scenes:*+"
        "x:scenes:*+r:rules:*+w:rules:*+sse+r:installedapps:*+"
        "w:installedapps:*"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
            "access_tier": 0,
            "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    result["data"]["token"].pop("expires_at")
    assert result["data"][CONF_TOKEN] == {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "token_type": "Bearer",
        "expires_in": 82806,
        "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
        "r:locations:* w:locations:* x:locations:* "
        "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
        "access_tier": 0,
        "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
    }
    assert result["result"].unique_id == "397678e5-9995-4a39-9d9f-ae6ba310236c"


@pytest.mark.usefixtures("current_request_with_host", "use_cloud", "mock_setup_entry")
async def test_not_enough_scopes(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
) -> None:
    """Test we abort if we don't have enough scopes."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        "https://api.smartthings.com/oauth/authorize"
        "?response_type=code&client_id=CLIENT_ID"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=r:devices:*+w:devices:*+x:devices:*+r:hubs:*+"
        "r:locations:*+w:locations:*+x:locations:*+r:scenes:*+"
        "x:scenes:*+r:rules:*+w:rules:*+sse+r:installedapps:*+"
        "w:installedapps:*"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* "
            "r:installedapps:* w:installedapps:*",
            "access_tier": 0,
            "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_scopes"


@pytest.mark.usefixtures("current_request_with_host", "use_cloud", "mock_setup_entry")
async def test_duplicate_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate entry is not able to set up."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        "https://api.smartthings.com/oauth/authorize"
        "?response_type=code&client_id=CLIENT_ID"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=r:devices:*+w:devices:*+x:devices:*+r:hubs:*+"
        "r:locations:*+w:locations:*+x:locations:*+r:scenes:*+"
        "x:scenes:*+r:rules:*+w:rules:*+sse+r:installedapps:*+"
        "w:installedapps:*"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
            "access_tier": 0,
            "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_no_cloud_no_credential_prompts_for_pat(
    hass: HomeAssistant,
) -> None:
    """Check the PAT form is shown when there is no cloud and no stored credential."""
    with patch(
        "homeassistant.components.smartthings.config_flow.async_get_implementations",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pat"
    pat_field = next(iter(result["data_schema"].schema))
    assert result["data_schema"].schema[pat_field].config["type"] == "password"


@pytest.mark.usefixtures("current_request_with_host", "use_cloud", "mock_setup_entry")
async def test_reauthentication(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test SmartThings reauthentication."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* sse w:rules:*",
            "access_tier": 0,
            "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    mock_config_entry.data["token"].pop("expires_at")
    assert mock_config_entry.data[CONF_TOKEN] == {
        "refresh_token": "new-refresh-token",
        "access_token": "new-access-token",
        "token_type": "Bearer",
        "expires_in": 82806,
        "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
        "r:locations:* w:locations:* x:locations:* "
        "r:scenes:* x:scenes:* r:rules:* sse w:rules:*",
        "access_tier": 0,
        "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
    }


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauthentication_cloud_entry_offers_picker(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthenticating a cloud entry can move it to a stored credential."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, "auth_implementation": "cloud"},
    )
    implementations = await config_entry_oauth2_flow.async_get_implementations(
        hass, DOMAIN
    )
    cloud_implementation = SimpleNamespace(domain="cloud", name="Nabu Casa Cloud")

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    # The cloud implementation stays available for existing cloud entries.
    with (
        patch(
            "homeassistant.components.smartthings.config_flow.async_get_implementations",
            return_value={"cloud": cloud_implementation, **implementations},
        ),
        patch(
            "homeassistant.components.smartthings.config_flow.async_get_config_entry_implementation",
            return_value=cloud_implementation,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pick_implementation"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"implementation": "pat"}
        )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert "client_id=CLIENT_ID" in result["url"]

    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": result["flow_id"], "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* sse w:rules:*",
            "access_tier": 0,
            "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data["auth_implementation"] == DOMAIN


@pytest.mark.usefixtures("current_request_with_host", "use_cloud", "mock_setup_entry")
async def test_reauthentication_wrong_scopes(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test SmartThings reauthentication with wrong scopes."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* "
            "r:installedapps:* w:installedapps:*",
            "access_tier": 0,
            "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_scopes"


@pytest.mark.usefixtures("current_request_with_host", "use_cloud", "mock_setup_entry")
async def test_reauth_account_mismatch(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test SmartThings reauthentication with different account."""
    mock_config_entry.add_to_hass(hass)

    mock_smartthings.get_locations.return_value[
        0
    ].location_id = "123123123-2be1-4e40-b257-e4ef59083324"

    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
            "access_tier": 0,
            "installed_app_id": "123123123-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_account_mismatch"


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauthentication_no_cloud_uses_stored_credential(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test SmartThings reauthentication without cloud uses the stored credential."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.EXTERNAL_STEP


@pytest.mark.usefixtures("current_request_with_host", "use_cloud")
async def test_migration(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_old_config_entry: MockConfigEntry,
) -> None:
    """Test SmartThings reauthentication with different account."""
    mock_old_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_old_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_old_config_entry.state is ConfigEntryState.SETUP_ERROR

    result = hass.config_entries.flow.async_progress()[0]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
            "access_tier": 0,
            "installed_app_id": "123123123-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_old_config_entry.state is ConfigEntryState.LOADED
    assert len(hass.config_entries.flow.async_progress()) == 0
    mock_old_config_entry.data[CONF_TOKEN].pop("expires_at")
    assert mock_old_config_entry.data == {
        "auth_implementation": DOMAIN,
        "old_data": {CONF_LOCATION_ID: "397678e5-9995-4a39-9d9f-ae6ba310236c"},
        CONF_TOKEN: {
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
            "access_tier": 0,
            "installed_app_id": "123123123-2be1-4e40-b257-e4ef59083324",
        },
        CONF_LOCATION_ID: "397678e5-9995-4a39-9d9f-ae6ba310236c",
        CONF_SUBSCRIPTION_ID: "f5768ce8-c9e5-4507-9020-912c0c60e0ab",
    }
    assert mock_old_config_entry.unique_id == "397678e5-9995-4a39-9d9f-ae6ba310236c"
    assert mock_old_config_entry.version == 3
    assert mock_old_config_entry.minor_version == 3
    mock_smartthings.get_installed_app.assert_called_once_with(
        "mock-access-token",
        "123aa123-2be1-4e40-b257-e4ef59083324",
    )
    mock_smartthings.delete_installed_app.assert_called_once_with(
        "mock-access-token",
        "123aa123-2be1-4e40-b257-e4ef59083324",
    )
    mock_smartthings.delete_smart_app.assert_called_once_with(
        "mock-access-token",
        "c6cde2b0-203e-44cf-a510-3b3ed4706996",
    )


@pytest.mark.usefixtures("current_request_with_host", "use_cloud")
async def test_migration_wrong_location(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_old_config_entry: MockConfigEntry,
) -> None:
    """Test SmartThings reauthentication with wrong location."""
    mock_old_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_old_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_old_config_entry.state is ConfigEntryState.SETUP_ERROR

    mock_smartthings.get_locations.return_value[
        0
    ].location_id = "123123123-2be1-4e40-b257-e4ef59083324"

    result = hass.config_entries.flow.async_progress()[0]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await hass_client_no_auth()
    await client.get(f"/auth/external/callback?code=abcd&state={state}")

    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "new-refresh-token",
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
            "access_tier": 0,
            "installed_app_id": "123123123-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_location_mismatch"
    assert mock_old_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_old_config_entry.data == {
        OLD_DATA: {CONF_LOCATION_ID: "397678e5-9995-4a39-9d9f-ae6ba310236c"}
    }
    assert (
        mock_old_config_entry.unique_id
        == "appid123-2be1-4e40-b257-e4ef59083324_397678e5-9995-4a39-9d9f-ae6ba310236c"
    )
    assert mock_old_config_entry.version == 3
    assert mock_old_config_entry.minor_version == 3
    mock_smartthings.get_installed_app.assert_called_once_with(
        "mock-access-token",
        "123aa123-2be1-4e40-b257-e4ef59083324",
    )
    mock_smartthings.delete_installed_app.assert_called_once_with(
        "mock-access-token",
        "123aa123-2be1-4e40-b257-e4ef59083324",
    )
    mock_smartthings.delete_smart_app.assert_called_once_with(
        "mock-access-token",
        "c6cde2b0-203e-44cf-a510-3b3ed4706996",
    )


@pytest.mark.usefixtures("current_request_with_host")
async def test_migration_no_cloud_uses_stored_credential(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
    mock_old_config_entry: MockConfigEntry,
) -> None:
    """Test SmartThings reauthentication with different account."""
    mock_old_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_old_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_old_config_entry.state is ConfigEntryState.SETUP_ERROR

    result = hass.config_entries.flow.async_progress()[0]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.EXTERNAL_STEP


@pytest.mark.usefixtures("current_request_with_host", "use_cloud", "mock_setup_entry")
async def test_dhcp_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_smartthings: AsyncMock,
) -> None:
    """Check a full flow initiated by DHCP discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.0.2", hostname="Samsung-Washer", macaddress="88571dc3ed7d"
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "oauth_discovery"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        "https://api.smartthings.com/oauth/authorize"
        "?response_type=code&client_id=CLIENT_ID"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=r:devices:*+w:devices:*+x:devices:*+r:hubs:*+"
        "r:locations:*+w:locations:*+x:locations:*+r:scenes:*+"
        "x:scenes:*+r:rules:*+w:rules:*+sse+r:installedapps:*+"
        "w:installedapps:*"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://auth-global.api.smartthings.com/oauth/token",
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 82806,
            "scope": "r:devices:* w:devices:* x:devices:* r:hubs:* "
            "r:locations:* w:locations:* x:locations:* "
            "r:scenes:* x:scenes:* r:rules:* w:rules:* sse",
            "access_tier": 0,
            "installed_app_id": "5aaaa925-2be1-4e40-b257-e4ef59083324",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "397678e5-9995-4a39-9d9f-ae6ba310236c"


@pytest.mark.usefixtures("current_request_with_host", "use_cloud")
async def test_duplicate_entry_dhcp(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test duplicate entry is not able to set up."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.0.2", hostname="Samsung-Washer", macaddress="88571dc3ed7d"
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
