"""Test the fitbit config flow."""

from collections.abc import Awaitable, Callable
from http import HTTPStatus
from unittest.mock import patch

from requests_mock.mocker import Mocker

from homeassistant import config_entries
from homeassistant.components.fitbit.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow, issue_registry as ir

from .conftest import (
    CLIENT_ID,
    FAKE_ACCESS_TOKEN,
    FAKE_AUTH_IMPL,
    FAKE_REFRESH_TOKEN,
    PROFILE_API_URL,
    PROFILE_USER_ID,
)

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

REDIRECT_URL = "https://example.com/auth/external/callback"

# These constants differ from values in the config entry or fitbit.conf
SERVER_ACCESS_TOKEN = {
    "refresh_token": "server-access-token",
    "access_token": "server-refresh-token",
    "type": "Bearer",
    "expires_in": 60,
}


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
    assert result["type"] == FlowResultType.EXTERNAL_STEP
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
    assert config_entry.title == "My name"
    assert config_entry.unique_id == PROFILE_USER_ID

    data = dict(config_entry.data)
    assert "token" in data
    del data["token"]["expires_at"]
    assert dict(config_entry.data) == {
        "auth_implementation": FAKE_AUTH_IMPL,
        "token": SERVER_ACCESS_TOKEN,
    }


async def test_api_failure(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    requests_mock: Mocker,
    setup_credentials: None,
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
    assert result["type"] == FlowResultType.EXTERNAL_STEP
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
        "GET", PROFILE_API_URL, status_code=HTTPStatus.INTERNAL_SERVER_ERROR
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"


async def test_import_fitbit_config(
    hass: HomeAssistant,
    fitbit_config_setup: None,
    sensor_platform_setup: Callable[[], Awaitable[bool]],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that platform configuration is imported successfully."""

    with patch(
        "homeassistant.components.fitbit.async_setup_entry", return_value=True
    ) as mock_setup:
        await sensor_platform_setup()

    assert len(mock_setup.mock_calls) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    # Verify valid profile can be fetched from the API
    config_entry = entries[0]
    assert config_entry.title == "My name"
    assert config_entry.unique_id == PROFILE_USER_ID

    data = dict(config_entry.data)
    assert "token" in data
    del data["token"]["expires_at"]
    # Verify imported values from fitbit.conf and configuration.yaml
    assert dict(config_entry.data) == {
        "auth_implementation": DOMAIN,
        "clock_format": "24H",
        "monitored_resources": ["activities/steps"],
        "token": {
            "access_token": FAKE_ACCESS_TOKEN,
            "refresh_token": FAKE_REFRESH_TOKEN,
        },
        "unit_system": "default",
    }

    # Verify an issue is raised for deprecated configuration.yaml
    assert (DOMAIN, "deprecated_yaml_import") in issue_registry.issues


async def test_import_fitbit_config_failure_cannot_connect(
    hass: HomeAssistant,
    fitbit_config_setup: None,
    sensor_platform_setup: Callable[[], Awaitable[bool]],
    issue_registry: ir.IssueRegistry,
    requests_mock: Mocker,
) -> None:
    """Test that platform configuration is imported successfully."""

    requests_mock.register_uri(
        "GET", PROFILE_API_URL, status_code=HTTPStatus.INTERNAL_SERVER_ERROR
    )

    with patch(
        "homeassistant.components.fitbit.async_setup_entry", return_value=True
    ) as mock_setup:
        await sensor_platform_setup()

    assert len(mock_setup.mock_calls) == 0

    # Verify an issue is raised that we were unable to import configuration
    assert (
        DOMAIN,
        "deprecated_yaml_import_issue_cannot_connect",
    ) in issue_registry.issues


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
    assert (DOMAIN, "deprecated_yaml_no_import") in issue_registry.issues
