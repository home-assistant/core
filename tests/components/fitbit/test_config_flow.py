"""Test the fitbit config flow."""

from collections.abc import Awaitable, Callable
from http import HTTPStatus
import time
from typing import Any
from unittest.mock import patch

import pytest
from requests_mock.mocker import Mocker

from homeassistant import config_entries
from homeassistant.components.fitbit.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow, issue_registry as ir

from .conftest import (
    CLIENT_ID,
    DISPLAY_NAME,
    FAKE_AUTH_IMPL,
    PROFILE_API_URL,
    PROFILE_DATA,
    PROFILE_USER_ID,
    SERVER_ACCESS_TOKEN,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REDIRECT_URL = "https://example.com/auth/external/callback"


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    profile: None,
    setup_credentials: None,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URL,
        },
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URL}"
        f"&state={state}"
        "&scope=activity+heartrate+nutrition+profile+settings+sleep+weight&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json=SERVER_ACCESS_TOKEN,
    )

    with patch(
        "homeassistant.components.fitbit.async_setup_entry", return_value=True
    ) as mock_setup:
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(mock_setup.mock_calls) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    config_entry = entries[0]
    assert config_entry.title == DISPLAY_NAME
    assert config_entry.unique_id == PROFILE_USER_ID

    data = dict(config_entry.data)
    assert "token" in data
    del data["token"]["expires_at"]
    assert dict(config_entry.data) == {
        "auth_implementation": FAKE_AUTH_IMPL,
        "token": SERVER_ACCESS_TOKEN,
    }


@pytest.mark.parametrize(
    ("status_code", "error_reason"),
    [
        (HTTPStatus.UNAUTHORIZED, "invalid_auth"),
        (HTTPStatus.INTERNAL_SERVER_ERROR, "cannot_connect"),
    ],
)
async def test_token_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    profile: None,
    setup_credentials: None,
    status_code: HTTPStatus,
    error_reason: str,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URL,
        },
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URL}"
        f"&state={state}"
        "&scope=activity+heartrate+nutrition+profile+settings+sleep+weight&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        status=status_code,
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == error_reason


@pytest.mark.parametrize(
    ("http_status", "json", "error_reason"),
    [
        (HTTPStatus.INTERNAL_SERVER_ERROR, None, "cannot_connect"),
        (HTTPStatus.FORBIDDEN, None, "cannot_connect"),
        (
            HTTPStatus.UNAUTHORIZED,
            {
                "errors": [{"errorType": "invalid_grant"}],
            },
            "invalid_access_token",
        ),
    ],
)
async def test_api_failure(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    requests_mock: Mocker,
    setup_credentials: None,
    http_status: HTTPStatus,
    json: Any,
    error_reason: str,
) -> None:
    """Test a failure to fetch the profile during the setup flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URL,
        },
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URL}"
        f"&state={state}"
        "&scope=activity+heartrate+nutrition+profile+settings+sleep+weight&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json=SERVER_ACCESS_TOKEN,
    )

    requests_mock.register_uri(
        "GET",
        PROFILE_API_URL,
        status_code=http_status,
        json=json,
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == error_reason


async def test_config_entry_already_exists(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    requests_mock: Mocker,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
) -> None:
    """Test that an account may only be configured once."""

    # Verify existing config entry
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URL,
        },
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URL}"
        f"&state={state}"
        "&scope=activity+heartrate+nutrition+profile+settings+sleep+weight&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json=SERVER_ACCESS_TOKEN,
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.parametrize(
    "token_expiration_time",
    [time.time() + 86400, time.time() - 86400],
    ids=("token_active", "token_expired"),
)
async def test_import_fitbit_config(
    hass: HomeAssistant,
    fitbit_config_setup: None,
    sensor_platform_setup: Callable[[], Awaitable[bool]],
    issue_registry: ir.IssueRegistry,
    requests_mock: Mocker,
) -> None:
    """Test that platform configuration is imported successfully."""

    requests_mock.register_uri(
        "POST",
        OAUTH2_TOKEN,
        status_code=HTTPStatus.OK,
        json=SERVER_ACCESS_TOKEN,
    )

    with patch(
        "homeassistant.components.fitbit.async_setup_entry", return_value=True
    ) as mock_setup:
        await sensor_platform_setup()

    assert len(mock_setup.mock_calls) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    # Verify valid profile can be fetched from the API
    config_entry = entries[0]
    assert config_entry.title == DISPLAY_NAME
    assert config_entry.unique_id == PROFILE_USER_ID

    data = dict(config_entry.data)
    # Verify imported values from fitbit.conf and configuration.yaml and
    # that the token is updated.
    assert "token" in data
    expires_at = data["token"]["expires_at"]
    assert expires_at > time.time()
    del data["token"]["expires_at"]
    assert dict(config_entry.data) == {
        "auth_implementation": DOMAIN,
        "clock_format": "24H",
        "monitored_resources": ["activities/steps"],
        "token": {
            "access_token": "server-access-token",
            "refresh_token": "server-refresh-token",
            "scope": "activity heartrate nutrition profile settings sleep weight",
        },
        "unit_system": "default",
    }

    # Verify an issue is raised for deprecated configuration.yaml
    issue = issue_registry.issues.get((DOMAIN, "deprecated_yaml"))
    assert issue
    assert issue.translation_key == "deprecated_yaml_import"


async def test_import_fitbit_config_failure_cannot_connect(
    hass: HomeAssistant,
    fitbit_config_setup: None,
    sensor_platform_setup: Callable[[], Awaitable[bool]],
    issue_registry: ir.IssueRegistry,
    requests_mock: Mocker,
) -> None:
    """Test platform configuration fails to import successfully."""

    requests_mock.register_uri(
        "POST",
        OAUTH2_TOKEN,
        status_code=HTTPStatus.OK,
        json=SERVER_ACCESS_TOKEN,
    )
    requests_mock.register_uri(
        "GET", PROFILE_API_URL, status_code=HTTPStatus.INTERNAL_SERVER_ERROR
    )

    with patch(
        "homeassistant.components.fitbit.async_setup_entry", return_value=True
    ) as mock_setup:
        await sensor_platform_setup()

    assert len(mock_setup.mock_calls) == 0

    # Verify an issue is raised that we were unable to import configuration
    issue = issue_registry.issues.get((DOMAIN, "deprecated_yaml"))
    assert issue
    assert issue.translation_key == "deprecated_yaml_import_issue_cannot_connect"


@pytest.mark.parametrize(
    "status_code",
    [
        (HTTPStatus.UNAUTHORIZED),
        (HTTPStatus.INTERNAL_SERVER_ERROR),
    ],
)
async def test_import_fitbit_config_cannot_refresh(
    hass: HomeAssistant,
    fitbit_config_setup: None,
    sensor_platform_setup: Callable[[], Awaitable[bool]],
    issue_registry: ir.IssueRegistry,
    requests_mock: Mocker,
    status_code: HTTPStatus,
) -> None:
    """Test platform configuration import fails when refreshing the token."""

    requests_mock.register_uri(
        "POST",
        OAUTH2_TOKEN,
        status_code=status_code,
        json="",
    )

    with patch(
        "homeassistant.components.fitbit.async_setup_entry", return_value=True
    ) as mock_setup:
        await sensor_platform_setup()

    assert len(mock_setup.mock_calls) == 0

    # Verify an issue is raised that we were unable to import configuration
    issue = issue_registry.issues.get((DOMAIN, "deprecated_yaml"))
    assert issue
    assert issue.translation_key == "deprecated_yaml_import_issue_cannot_connect"


async def test_import_fitbit_config_already_exists(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    fitbit_config_setup: None,
    sensor_platform_setup: Callable[[], Awaitable[bool]],
    issue_registry: ir.IssueRegistry,
    requests_mock: Mocker,
) -> None:
    """Test that platform configuration is not imported if it already exists."""

    requests_mock.register_uri(
        "POST",
        OAUTH2_TOKEN,
        status_code=HTTPStatus.OK,
        json=SERVER_ACCESS_TOKEN,
    )

    # Verify existing config entry
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    with patch(
        "homeassistant.components.fitbit.async_setup_entry", return_value=True
    ) as mock_config_entry_setup:
        await integration_setup()

    assert len(mock_config_entry_setup.mock_calls) == 1

    with patch(
        "homeassistant.components.fitbit.async_setup_entry", return_value=True
    ) as mock_import_setup:
        await sensor_platform_setup()

    assert len(mock_import_setup.mock_calls) == 0

    # Still one config entry
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    # Verify an issue is raised for deprecated configuration.yaml
    issue = issue_registry.issues.get((DOMAIN, "deprecated_yaml"))
    assert issue
    assert issue.translation_key == "deprecated_yaml_import"


async def test_platform_setup_without_import(
    hass: HomeAssistant,
    sensor_platform_setup: Callable[[], Awaitable[bool]],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test platform configuration.yaml but no existing fitbit.conf credentials."""

    with patch(
        "homeassistant.components.fitbit.async_setup_entry", return_value=True
    ) as mock_setup:
        await sensor_platform_setup()

    # Verify no configuration entry is imported since the integration is not
    # fully setup properly
    assert len(mock_setup.mock_calls) == 0
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 0

    # Verify an issue is raised for deprecated configuration.yaml
    assert len(issue_registry.issues) == 1
    issue = issue_registry.issues.get((DOMAIN, "deprecated_yaml"))
    assert issue
    assert issue.translation_key == "deprecated_yaml_no_import"


async def test_reauth_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    profile: None,
    setup_credentials: None,
) -> None:
    """Test OAuth reauthentication flow will update existing config entry."""
    config_entry.add_to_hass(hass)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    # config_entry.req initiates reauth
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URL,
        },
    )
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URL}"
        f"&state={state}"
        "&scope=activity+heartrate+nutrition+profile+settings+sleep+weight&prompt=none"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "updated-refresh-token",
            "access_token": "updated-access-token",
            "type": "Bearer",
            "expires_in": "60",
        },
    )

    with patch(
        "homeassistant.components.fitbit.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1

    assert config_entry.data["token"]["refresh_token"] == "updated-refresh-token"


@pytest.mark.parametrize("profile_id", ["other-user-id"])
async def test_reauth_wrong_user_id(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    profile: None,
    setup_credentials: None,
) -> None:
    """Test OAuth reauthentication where the wrong user is selected."""
    config_entry.add_to_hass(hass)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URL,
        },
    )
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URL}"
        f"&state={state}"
        "&scope=activity+heartrate+nutrition+profile+settings+sleep+weight&prompt=none"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "updated-refresh-token",
            "access_token": "updated-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.fitbit.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "wrong_account"

    assert len(mock_setup.mock_calls) == 0


@pytest.mark.parametrize(
    ("profile_data", "expected_title"),
    [
        (PROFILE_DATA, DISPLAY_NAME),
        ({"displayName": DISPLAY_NAME}, DISPLAY_NAME),
    ],
    ids=("full_profile_data", "display_name_only"),
)
async def test_partial_profile_data(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    profile: None,
    setup_credentials: None,
    expected_title: str,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URL,
        },
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URL}"
        f"&state={state}"
        "&scope=activity+heartrate+nutrition+profile+settings+sleep+weight&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json=SERVER_ACCESS_TOKEN,
    )

    with patch(
        "homeassistant.components.fitbit.async_setup_entry", return_value=True
    ) as mock_setup:
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(mock_setup.mock_calls) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    config_entry = entries[0]
    assert config_entry.title == expected_title
