"""Test the google config flow."""

from __future__ import annotations

from collections.abc import Callable
import datetime
from typing import Any
from unittest.mock import Mock, patch

from aiohttp.client_exceptions import ClientError
from freezegun.api import FrozenDateTimeFactory
from oauth2client.client import (
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
from homeassistant.components.google.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.util.dt import utcnow

from .conftest import ComponentSetup, YieldFixture

from tests.common import MockConfigEntry, async_fire_time_changed

CODE_CHECK_INTERVAL = 1
CODE_CHECK_ALARM_TIMEDELTA = datetime.timedelta(seconds=CODE_CHECK_INTERVAL * 2)
EMAIL_ADDRESS = "user@gmail.com"


@pytest.fixture(autouse=True)
async def request_setup(current_request_with_host) -> None:
    """Request setup."""
    return


@pytest.fixture
async def code_expiration_delta() -> datetime.timedelta:
    """Fixture for code expiration time, defaulting to the future."""
    return datetime.timedelta(minutes=3)


@pytest.fixture
async def mock_code_flow(
    code_expiration_delta: datetime.timedelta,
) -> YieldFixture[Mock]:
    """Fixture for initiating OAuth flow."""
    with patch(
        "oauth2client.client.OAuth2WebServerFlow.step1_get_device_and_user_codes",
    ) as mock_flow:
        mock_flow.return_value.user_code_expiry = utcnow() + code_expiration_delta
        mock_flow.return_value.interval = CODE_CHECK_INTERVAL
        yield mock_flow


@pytest.fixture
async def mock_exchange(creds: OAuth2Credentials) -> YieldFixture[Mock]:
    """Fixture for mocking out the exchange for credentials."""
    with patch(
        "oauth2client.client.OAuth2WebServerFlow.step2_exchange", return_value=creds
    ) as mock:
        yield mock


@pytest.fixture
async def primary_calendar_error() -> ClientError | None:
    """Fixture for tests to inject an error during calendar lookup."""
    return None


@pytest.fixture(autouse=True)
async def primary_calendar(
    mock_calendar_get: Callable[[...], None], primary_calendar_error: ClientError | None
) -> None:
    """Fixture to return the primary calendar."""
    mock_calendar_get(
        "primary",
        {"id": EMAIL_ADDRESS, "summary": "Personal"},
        exc=primary_calendar_error,
    )


async def fire_alarm(hass, point_in_time):
    """Fire an alarm and wait for callbacks to run."""
    with patch("homeassistant.util.dt.utcnow", return_value=point_in_time):
        async_fire_time_changed(hass, point_in_time)
        await hass.async_block_till_done()


@pytest.mark.freeze_time("2022-06-03 15:19:59-00:00")
async def test_full_flow_yaml_creds(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    mock_exchange: Mock,
    component_setup: ComponentSetup,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test successful creds setup."""
    assert await component_setup()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "progress"
    assert result.get("step_id") == "auth"
    assert "description_placeholders" in result
    assert "url" in result["description_placeholders"]

    with patch(
        "homeassistant.components.google.async_setup_entry", return_value=True
    ) as mock_setup:
        # Run one tick to invoke the credential exchange check
        freezer.tick(CODE_CHECK_ALARM_TIMEDELTA)
        await fire_alarm(hass, datetime.datetime.utcnow())
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"]
        )

    assert result.get("type") == "create_entry"
    assert result.get("title") == EMAIL_ADDRESS
    assert "data" in result
    data = result["data"]
    assert "token" in data
    assert (
        data["token"]["expires_in"]
        == 60 * 60 - CODE_CHECK_ALARM_TIMEDELTA.total_seconds()
    )
    assert data["token"]["expires_at"] == 1654273199.0
    data["token"].pop("expires_at")
    data["token"].pop("expires_in")
    assert data == {
        "auth_implementation": "device_auth",
        "token": {
            "access_token": "ACCESS_TOKEN",
            "refresh_token": "REFRESH_TOKEN",
            "scope": "https://www.googleapis.com/auth/calendar",
            "token_type": "Bearer",
        },
    }
    assert result.get("options") == {"calendar_access": "read_write"}

    assert len(mock_setup.mock_calls) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


@pytest.mark.parametrize("google_config", [None])
async def test_full_flow_application_creds(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    mock_exchange: Mock,
    config: dict[str, Any],
    component_setup: ComponentSetup,
) -> None:
    """Test successful creds setup."""
    assert await component_setup()

    await async_import_client_credential(
        hass, DOMAIN, ClientCredential("client-id", "client-secret"), "imported-cred"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "progress"
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

    assert result.get("type") == "create_entry"
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
    }
    assert result.get("options") == {"calendar_access": "read_write"}

    assert len(mock_setup.mock_calls) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


async def test_code_error(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    component_setup: ComponentSetup,
) -> None:
    """Test successful creds setup."""
    assert await component_setup()

    with patch(
        "oauth2client.client.OAuth2WebServerFlow.step1_get_device_and_user_codes",
        side_effect=OAuth2DeviceCodeError("Test Failure"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result.get("type") == "abort"
        assert result.get("reason") == "oauth_error"


@pytest.mark.parametrize("code_expiration_delta", [datetime.timedelta(seconds=5)])
async def test_expired_after_exchange(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    component_setup: ComponentSetup,
) -> None:
    """Test credential exchange expires immediately."""
    assert await component_setup()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "progress"
    assert result.get("step_id") == "auth"
    assert "description_placeholders" in result
    assert "url" in result["description_placeholders"]

    with patch(
        "oauth2client.client.OAuth2WebServerFlow.step2_exchange",
        side_effect=FlowExchangeError(),
    ):
        now = utcnow()
        await fire_alarm(hass, now + datetime.timedelta(seconds=65))
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(flow_id=result["flow_id"])
    assert result.get("type") == "abort"
    assert result.get("reason") == "code_expired"


async def test_exchange_error(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    mock_exchange: Mock,
    component_setup: ComponentSetup,
) -> None:
    """Test an error while exchanging the code for credentials."""
    assert await component_setup()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "progress"
    assert result.get("step_id") == "auth"
    assert "description_placeholders" in result
    assert "url" in result["description_placeholders"]

    # Run one tick to invoke the credential exchange check
    now = utcnow()
    with patch(
        "oauth2client.client.OAuth2WebServerFlow.step2_exchange",
        side_effect=FlowExchangeError(),
    ):
        now += CODE_CHECK_ALARM_TIMEDELTA
        await fire_alarm(hass, now)
        await hass.async_block_till_done()

    # Status has not updated, will retry
    result = await hass.config_entries.flow.async_configure(flow_id=result["flow_id"])
    assert result.get("type") == "progress"
    assert result.get("step_id") == "auth"

    # Run another tick, which attempts credential exchange again
    with patch(
        "homeassistant.components.google.async_setup_entry", return_value=True
    ) as mock_setup:
        now += CODE_CHECK_ALARM_TIMEDELTA
        await fire_alarm(hass, now)
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"]
        )

    assert result.get("type") == "create_entry"
    assert result.get("title") == EMAIL_ADDRESS
    assert "data" in result
    data = result["data"]
    assert "token" in data
    data["token"].pop("expires_at")
    data["token"].pop("expires_in")
    assert data == {
        "auth_implementation": "device_auth",
        "token": {
            "access_token": "ACCESS_TOKEN",
            "refresh_token": "REFRESH_TOKEN",
            "scope": "https://www.googleapis.com/auth/calendar",
            "token_type": "Bearer",
        },
    }

    assert len(mock_setup.mock_calls) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


async def test_existing_config_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    component_setup: ComponentSetup,
) -> None:
    """Test can't configure when config entry already exists."""
    config_entry.add_to_hass(hass)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert await component_setup()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "abort"
    assert result.get("reason") == "already_configured"


async def test_missing_configuration(
    hass: HomeAssistant,
) -> None:
    """Test can't configure when no authentication source is available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "abort"
    assert result.get("reason") == "missing_credentials"


@pytest.mark.parametrize("google_config", [None])
async def test_missing_configuration_yaml_empty(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
) -> None:
    """Test setup with an empty yaml configuration and no credentials."""
    assert await component_setup()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "abort"
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
            "client-id",
            "client-secret",
            "http://example/authorize",
            "http://example/token",
        ),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "abort"
    assert result.get("reason") == "oauth_error"


async def test_import_config_entry_from_existing_token(
    hass: HomeAssistant,
    mock_token_read: None,
    component_setup: ComponentSetup,
) -> None:
    """Test setup with an existing token file."""
    assert await component_setup()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    data = entries[0].data
    assert "token" in data
    data["token"].pop("expires_at")
    data["token"].pop("expires_in")
    assert data == {
        "auth_implementation": "device_auth",
        "token": {
            "access_token": "ACCESS_TOKEN",
            "refresh_token": "REFRESH_TOKEN",
            "scope": "https://www.googleapis.com/auth/calendar",
            "token_type": "Bearer",
        },
    }


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    mock_exchange: Mock,
    component_setup: ComponentSetup,
) -> None:
    """Test can't configure when config entry already exists."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": "device_auth",
            "token": {"access_token": "OLD_ACCESS_TOKEN"},
        },
    )
    config_entry.add_to_hass(hass)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert await component_setup()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
        },
        data=config_entry.data,
    )
    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"],
        user_input={},
    )
    assert result.get("type") == "progress"
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

    assert result.get("type") == "abort"
    assert result.get("reason") == "reauth_successful"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    data = entries[0].data
    assert "token" in data
    data["token"].pop("expires_at")
    data["token"].pop("expires_in")
    assert data == {
        "auth_implementation": "device_auth",
        "token": {
            "access_token": "ACCESS_TOKEN",
            "refresh_token": "REFRESH_TOKEN",
            "scope": "https://www.googleapis.com/auth/calendar",
            "token_type": "Bearer",
        },
    }

    assert len(mock_setup.mock_calls) == 1


@pytest.mark.parametrize("primary_calendar_error", [ClientError()])
async def test_title_lookup_failure(
    hass: HomeAssistant,
    mock_code_flow: Mock,
    mock_exchange: Mock,
    component_setup: ComponentSetup,
) -> None:
    """Test successful config flow and title fetch fails gracefully."""
    assert await component_setup()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "progress"
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

    assert result.get("type") == "create_entry"
    assert result.get("title") == "Import from configuration.yaml"

    assert len(mock_setup.mock_calls) == 1
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


async def test_options_flow_triggers_reauth(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    config_entry: MockConfigEntry,
) -> None:
    """Test load and unload of a ConfigEntry."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.google.async_setup_entry", return_value=True
    ) as mock_setup:
        await component_setup()
        mock_setup.assert_called_once()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.options == {}  # Default is read_write

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"
    data_schema = result["data_schema"].schema
    assert set(data_schema) == {"calendar_access"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "calendar_access": "read_only",
        },
    )
    assert result["type"] == "create_entry"
    assert config_entry.options == {"calendar_access": "read_only"}


async def test_options_flow_no_changes(
    hass: HomeAssistant,
    component_setup: ComponentSetup,
    config_entry: MockConfigEntry,
) -> None:
    """Test load and unload of a ConfigEntry."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.google.async_setup_entry", return_value=True
    ) as mock_setup:
        await component_setup()
        mock_setup.assert_called_once()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.options == {}  # Default is read_write

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "calendar_access": "read_write",
        },
    )
    assert result["type"] == "create_entry"
    assert config_entry.options == {"calendar_access": "read_write"}
