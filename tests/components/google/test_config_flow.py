"""Test the google config flow."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import datetime
from http import HTTPStatus
from typing import Any
from unittest.mock import Mock, patch

from aiohttp.client_exceptions import ClientError
from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
from oauth2client.client import (
    DeviceFlowInfo,
    FlowExchangeError,
    OAuth2Credentials,
    OAuth2DeviceCodeError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.google.const import (
    CONF_CREDENTIAL_TYPE,
    DOMAIN,
    CredentialType,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .conftest import CLIENT_ID, CLIENT_SECRET, EMAIL_ADDRESS, AsyncYieldFixture

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CODE_CHECK_INTERVAL = 1
CODE_CHECK_ALARM_TIMEDELTA = datetime.timedelta(seconds=CODE_CHECK_INTERVAL * 2)
OAUTH2_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH2_TOKEN = "https://oauth2.googleapis.com/token"


@pytest.fixture(autouse=True)
async def request_setup(current_request_with_host: None) -> None:
    """Request setup."""


@pytest.fixture(autouse=True)
async def setup_app_creds(hass: HomeAssistant) -> None:
    """Fixture to setup application credentials component."""
    await async_setup_component(hass, "application_credentials", {})


@pytest.fixture
async def code_expiration_delta() -> datetime.timedelta:
    """Fixture for code expiration time, defaulting to the future."""
    return datetime.timedelta(minutes=3)


@pytest.fixture
async def mock_code_flow(
    code_expiration_delta: datetime.timedelta,
) -> AsyncYieldFixture[Mock]:
    """Fixture for initiating OAuth flow."""
    with patch(
        "homeassistant.components.google.api.OAuth2WebServerFlow.step1_get_device_and_user_codes",
    ) as mock_flow:
        mock_flow.return_value = DeviceFlowInfo.FromResponse(
            {
                "device_code": "4/4-GMMhmHCXhWEzkobqIHGG_EnNYYsAkukHspeYUk9E8",
                "user_code": "GQVQ-JKEC",
                "verification_url": "https://www.google.com/device",
                "expires_in": code_expiration_delta.total_seconds(),
                "interval": CODE_CHECK_INTERVAL,
            }
        )
        yield mock_flow


@pytest.fixture
async def mock_exchange(creds: OAuth2Credentials) -> AsyncYieldFixture[Mock]:
    """Fixture for mocking out the exchange for credentials."""
    with patch(
        "homeassistant.components.google.api.OAuth2WebServerFlow.step2_exchange",
        return_value=creds,
    ) as mock:
        yield mock


@pytest.fixture
async def primary_calendar_email() -> str:
    """Fixture to override the google calendar primary email address."""
    return EMAIL_ADDRESS


@pytest.fixture
async def primary_calendar_error() -> ClientError | None:
    """Fixture for tests to inject an error during calendar lookup."""
    return None


@pytest.fixture
async def primary_calendar_status() -> HTTPStatus | None:
    """Fixture for tests to inject an error during calendar lookup."""
    return HTTPStatus.OK


@pytest.fixture(autouse=True)
async def primary_calendar(
    mock_calendar_get: Callable[..., None],
    primary_calendar_error: ClientError | None,
    primary_calendar_status: HTTPStatus | None,
    primary_calendar_email: str,
) -> None:
    """Fixture to return the primary calendar."""
    mock_calendar_get(
        "primary",
        {"id": primary_calendar_email, "summary": "Personal", "accessRole": "owner"},
        exc=primary_calendar_error,
        status=primary_calendar_status,
    )


async def fire_alarm(hass: HomeAssistant, point_in_time: datetime.datetime) -> None:
    """Fire an alarm and wait for callbacks to run."""
    with freeze_time(point_in_time):
        async_fire_time_changed(hass, point_in_time)
        await hass.async_block_till_done()


async def test_full_flow_application_creds(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    mock_exchange: Mock,
) -> None:
    """Test successful creds setup."""
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET), "imported-cred"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.SHOW_PROGRESS
    assert result.get("step_id") == "auth"
    assert "description_placeholders" in result
    assert "url" in result["description_placeholders"]

    with patch(
        "homeassistant.components.google.async_setup_entry", return_value=True
    ) as mock_setup:
        # Run one tick to invoke the credential exchange check
        now = utcnow()
        await fire_alarm(hass, now + CODE_CHECK_ALARM_TIMEDELTA)
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"]
        )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == EMAIL_ADDRESS
    assert "data" in result
    data = result["data"]
    assert "token" in data
    assert 0 < data["token"]["expires_in"] < 8 * 86400
    assert (
        datetime.datetime.now().timestamp()
        <= data["token"]["expires_at"]
        < (datetime.datetime.now() + datetime.timedelta(days=8)).timestamp()
    )
    data["token"].pop("expires_at")
    data["token"].pop("expires_in")
    assert data == {
        "auth_implementation": "imported-cred",
        "token": {
            "access_token": "ACCESS_TOKEN",
            "refresh_token": "REFRESH_TOKEN",
            "scope": "https://www.googleapis.com/auth/calendar",
            "token_type": "Bearer",
        },
        "credential_type": "device_auth",
    }
    assert result.get("options") == {"calendar_access": "read_write"}

    assert len(mock_setup.mock_calls) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


async def test_code_error(
    hass: HomeAssistant,
    mock_code_flow: Mock,
) -> None:
    """Test server error setting up the oauth flow."""
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET), "imported-cred"
    )

    with patch(
        "homeassistant.components.google.api.OAuth2WebServerFlow.step1_get_device_and_user_codes",
        side_effect=OAuth2DeviceCodeError("Test Failure"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result.get("type") is FlowResultType.ABORT
        assert result.get("reason") == "oauth_error"


async def test_timeout_error(
    hass: HomeAssistant,
    mock_code_flow: Mock,
) -> None:
    """Test timeout error setting up the oauth flow."""
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET), "imported-cred"
    )

    with patch(
        "homeassistant.components.google.api.OAuth2WebServerFlow.step1_get_device_and_user_codes",
        side_effect=TimeoutError(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result.get("type") is FlowResultType.ABORT
        assert result.get("reason") == "timeout_connect"


@pytest.mark.parametrize("code_expiration_delta", [datetime.timedelta(seconds=50)])
async def test_expired_after_exchange(
    hass: HomeAssistant,
    mock_code_flow: Mock,
) -> None:
    """Test credential exchange expires."""
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.SHOW_PROGRESS
    assert result.get("step_id") == "auth"
    assert "description_placeholders" in result
    assert "url" in result["description_placeholders"]

    # Fail first attempt then advance clock past exchange timeout
    with patch(
        "homeassistant.components.google.api.OAuth2WebServerFlow.step2_exchange",
        side_effect=FlowExchangeError(),
    ):
        now = utcnow()
        await fire_alarm(hass, now + datetime.timedelta(seconds=65))
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(flow_id=result["flow_id"])
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "code_expired"


async def test_exchange_error(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    mock_exchange: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an error while exchanging the code for credentials."""
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.SHOW_PROGRESS
    assert result.get("step_id") == "auth"
    assert "description_placeholders" in result
    assert "url" in result["description_placeholders"]

    # Run one tick to invoke the credential exchange check
    step2_exchange_called = asyncio.Event()

    def step2_exchange(*args, **kwargs):
        hass.loop.call_soon_threadsafe(step2_exchange_called.set)
        raise FlowExchangeError

    with patch(
        "homeassistant.components.google.api.OAuth2WebServerFlow.step2_exchange",
        side_effect=step2_exchange,
    ):
        freezer.tick(CODE_CHECK_ALARM_TIMEDELTA)
        async_fire_time_changed(hass, utcnow())
        await step2_exchange_called.wait()

    # Status has not updated, will retry
    result = await hass.config_entries.flow.async_configure(flow_id=result["flow_id"])
    assert result.get("type") is FlowResultType.SHOW_PROGRESS
    assert result.get("step_id") == "auth"

    # Run another tick, which attempts credential exchange again
    with patch(
        "homeassistant.components.google.async_setup_entry", return_value=True
    ) as mock_setup:
        freezer.tick(CODE_CHECK_ALARM_TIMEDELTA)
        async_fire_time_changed(hass, utcnow())
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"]
        )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == EMAIL_ADDRESS
    assert "data" in result
    data = result["data"]
    assert "token" in data
    data["token"].pop("expires_at")
    data["token"].pop("expires_in")
    assert data == {
        "auth_implementation": DOMAIN,
        "token": {
            "access_token": "ACCESS_TOKEN",
            "refresh_token": "REFRESH_TOKEN",
            "scope": "https://www.googleapis.com/auth/calendar",
            "token_type": "Bearer",
        },
        "credential_type": "device_auth",
    }

    assert len(mock_setup.mock_calls) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


async def test_duplicate_config_entries(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    mock_exchange: Mock,
    config_entry: MockConfigEntry,
) -> None:
    """Test that the same account cannot be setup twice."""
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET)
    )

    # Load a config entry
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.google.async_setup_entry", return_value=True
    ) as mock_setup:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    # Start a new config flow using the same credential
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.SHOW_PROGRESS
    assert result.get("step_id") == "auth"
    assert "description_placeholders" in result
    assert "url" in result["description_placeholders"]

    # Run one tick to invoke the credential exchange check
    now = utcnow()
    await fire_alarm(hass, now + CODE_CHECK_ALARM_TIMEDELTA)
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(flow_id=result["flow_id"])
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.parametrize("primary_calendar_email", ["another-email@example.com"])
async def test_multiple_config_entries(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    mock_exchange: Mock,
    config_entry: MockConfigEntry,
) -> None:
    """Test that multiple config entries can be set at once."""
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET)
    )

    # Load a config entry
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.google.async_setup_entry", return_value=True
    ) as mock_setup:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    # Start a new config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.SHOW_PROGRESS
    assert result.get("step_id") == "auth"
    assert "description_placeholders" in result
    assert "url" in result["description_placeholders"]

    with patch(
        "homeassistant.components.google.async_setup_entry", return_value=True
    ) as mock_setup:
        # Run one tick to invoke the credential exchange check
        now = utcnow()
        await fire_alarm(hass, now + CODE_CHECK_ALARM_TIMEDELTA)
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"]
        )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "another-email@example.com"
    assert len(mock_setup.mock_calls) == 1

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2


@pytest.mark.parametrize(  # Remove when translations fixed
    "ignore_translations",
    ["component.google.config.abort.missing_credentials"],
)
async def test_missing_configuration(
    hass: HomeAssistant,
) -> None:
    """Test can't configure when no authentication source is available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "missing_credentials"


async def test_wrong_configuration(
    hass: HomeAssistant,
) -> None:
    """Test can't use the wrong type of authentication."""

    # Google calendar flow currently only supports device auth
    config_entry_oauth2_flow.async_register_implementation(
        hass,
        DOMAIN,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            CLIENT_ID,
            CLIENT_SECRET,
            "http://example/authorize",
            "http://example/token",
        ),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "oauth_error"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    mock_exchange: Mock,
) -> None:
    """Test reauth of an existing config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "OLD_ACCESS_TOKEN"},
        },
    )
    config_entry.add_to_hass(hass)
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"],
        user_input={},
    )
    assert result.get("type") is FlowResultType.SHOW_PROGRESS
    assert result.get("step_id") == "auth"
    assert "description_placeholders" in result
    assert "url" in result["description_placeholders"]

    with patch(
        "homeassistant.components.google.async_setup_entry", return_value=True
    ) as mock_setup:
        # Run one tick to invoke the credential exchange check
        now = utcnow()
        await fire_alarm(hass, now + CODE_CHECK_ALARM_TIMEDELTA)
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"]
        )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    data = entries[0].data
    assert "token" in data
    data["token"].pop("expires_at")
    data["token"].pop("expires_in")
    assert data == {
        "auth_implementation": DOMAIN,
        "token": {
            "access_token": "ACCESS_TOKEN",
            "refresh_token": "REFRESH_TOKEN",
            "scope": "https://www.googleapis.com/auth/calendar",
            "token_type": "Bearer",
        },
        "credential_type": "device_auth",
    }

    assert len(mock_setup.mock_calls) == 1


@pytest.mark.parametrize(
    ("primary_calendar_error", "primary_calendar_status", "reason"),
    [
        (ClientError(), None, "cannot_connect"),
        (None, HTTPStatus.FORBIDDEN, "api_disabled"),
        (None, HTTPStatus.SERVICE_UNAVAILABLE, "cannot_connect"),
    ],
)
async def test_calendar_lookup_failure(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    mock_exchange: Mock,
    reason: str,
) -> None:
    """Test successful config flow and title fetch fails gracefully."""
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.SHOW_PROGRESS
    assert result.get("step_id") == "auth"
    assert "description_placeholders" in result
    assert "url" in result["description_placeholders"]

    with patch("homeassistant.components.google.async_setup_entry", return_value=True):
        # Run one tick to invoke the credential exchange check
        now = utcnow()
        await fire_alarm(hass, now + CODE_CHECK_ALARM_TIMEDELTA)
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"]
        )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == reason


async def test_options_flow_triggers_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test load and unload of a ConfigEntry."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.google.async_setup_entry", return_value=True
    ) as mock_setup:
        await hass.config_entries.async_setup(config_entry.entry_id)
        mock_setup.assert_called_once()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.options == {}  # Default is read_write

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    data_schema = result["data_schema"].schema
    assert set(data_schema) == {"calendar_access"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "calendar_access": "read_only",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {"calendar_access": "read_only"}


async def test_options_flow_no_changes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test load and unload of a ConfigEntry."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.google.async_setup_entry", return_value=True
    ) as mock_setup:
        await hass.config_entries.async_setup(config_entry.entry_id)
        mock_setup.assert_called_once()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.options == {}  # Default is read_write

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "calendar_access": "read_write",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {"calendar_access": "read_write"}


@pytest.mark.usefixtures("current_request_with_host")
async def test_web_auth_compatibility(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test that we can callback to web auth tokens."""
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )

    with patch(
        "homeassistant.components.google.api.OAuth2WebServerFlow.step1_get_device_and_user_codes",
        side_effect=OAuth2DeviceCodeError(
            "Invalid response 401. Error: invalid_client"
        ),
    ):
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
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=https://www.googleapis.com/auth/calendar"
        "&access_type=offline&prompt=consent"
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
            "scope": "https://www.googleapis.com/auth/calendar",
        },
    )

    with patch(
        "homeassistant.components.google.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    token = result.get("data", {}).get("token", {})
    del token["expires_at"]
    assert token == {
        "access_token": "mock-access-token",
        "expires_in": 60,
        "refresh_token": "mock-refresh-token",
        "type": "Bearer",
        "scope": "https://www.googleapis.com/auth/calendar",
    }
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.parametrize(
    "entry_data",
    [
        {},
        {CONF_CREDENTIAL_TYPE: CredentialType.WEB_AUTH},
    ],
)
async def test_web_reauth_flow(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    mock_exchange: Mock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
    entry_data: dict[str, Any],
) -> None:
    """Test reauth of an existing config entry with a web credential."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **entry_data,
            "auth_implementation": DOMAIN,
            "token": {"access_token": "OLD_ACCESS_TOKEN"},
        },
    )
    config_entry.add_to_hass(hass)
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET)
    )

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.google.api.OAuth2WebServerFlow.step1_get_device_and_user_codes",
        side_effect=OAuth2DeviceCodeError(
            "Invalid response 401. Error: invalid_client"
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"],
            user_input={},
        )

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    assert result.get("type") is FlowResultType.EXTERNAL_STEP
    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=https://www.googleapis.com/auth/calendar"
        "&access_type=offline&prompt=consent"
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
            "token_type": "Bearer",
            "expires_in": 60,
            "scope": "https://www.googleapis.com/auth/calendar",
        },
    )

    with patch(
        "homeassistant.components.google.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    data = dict(entries[0].data)
    data["token"].pop("expires_at")
    data["token"].pop("expires_in")
    assert data == {
        "auth_implementation": DOMAIN,
        "token": {
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "scope": "https://www.googleapis.com/auth/calendar",
            "token_type": "Bearer",
        },
        "credential_type": "web_auth",
    }

    assert len(mock_setup.mock_calls) == 1
