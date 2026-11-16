"""Test the CalDAV config flow."""

from collections.abc import Generator
from functools import partial
from unittest.mock import ANY, AsyncMock, Mock, patch

from caldav.lib.error import AuthorizationError, DAVError
from caldav.lib.http_sync import requests as caldav_requests
import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value

from homeassistant import config_entries
from homeassistant.components.caldav.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_PASSWORD, TEST_URL, TEST_USERNAME


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        f"homeassistant.components.{DOMAIN}.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    dav_client: Mock,
) -> None:
    """Test successful config flow setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert not result.get("errors")

    with patch.object(
        hass,
        "async_add_executor_job",
        wraps=hass.async_add_executor_job,
    ) as mock_add_executor_job:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_VERIFY_SSL: False,
            },
        )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == TEST_USERNAME
    assert result2.get("data") == {
        CONF_URL: TEST_URL,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_VERIFY_SSL: False,
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert any(
        isinstance(call.args[0], partial) and call.args[0].func is dav_client
        for call in mock_add_executor_job.call_args_list
    )


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (Exception(), "unknown"),
        (caldav_requests.exceptions.Timeout(), "cannot_connect"),
        (caldav_requests.exceptions.ConnectionError(), "cannot_connect"),
        (DAVError(), "cannot_connect"),
        (AuthorizationError(reason="Unauthorized"), "invalid_auth"),
        (AuthorizationError(reason="Other"), "cannot_connect"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_caldav_client_error(
    hass: HomeAssistant,
    side_effect: Exception,
    expected_error: str,
    dav_client: Mock,
) -> None:
    """Test CalDav client errors during configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    dav_client.return_value.get_principal.side_effect = side_effect

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("errors") == {"base": expected_error}

    dav_client.return_value.get_principal.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    await hass.async_block_till_done()

    assert result3.get("type") is FlowResultType.CREATE_ENTRY


async def test_reauth_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication configuration flow."""

    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password-2",
        },
    )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "reauth_successful"

    # Verify updated configuration entry
    assert dict(config_entry.data) == {
        CONF_URL: "https://example.com/url-1",
        CONF_USERNAME: "username-1",
        CONF_PASSWORD: "password-2",
        CONF_VERIFY_SSL: True,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_failure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    config_entry: MockConfigEntry,
    dav_client: Mock,
) -> None:
    """Test a failure during reauthentication configuration flow."""

    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    dav_client.return_value.get_principal.side_effect = DAVError

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password-2",
        },
    )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("errors") == {"base": "cannot_connect"}

    # Complete the form and it succeeds this time
    dav_client.return_value.get_principal.side_effect = None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "password-3",
        },
    )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "reauth_successful"

    # Verify updated configuration entry
    assert dict(config_entry.data) == {
        CONF_URL: "https://example.com/url-1",
        CONF_USERNAME: "username-1",
        CONF_PASSWORD: "password-3",
        CONF_VERIFY_SSL: True,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reconfigure_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    config_entry: MockConfigEntry,
    dav_client: Mock,
) -> None:
    """Test reconfiguring the server connection."""

    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    schema = result["data_schema"].schema
    assert get_schema_suggested_value(schema, CONF_URL) == TEST_URL
    assert get_schema_suggested_value(schema, CONF_PASSWORD) is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://example.com/url-2",
            CONF_PASSWORD: "password-2",
            CONF_VERIFY_SSL: False,
        },
    )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "reconfigure_successful"
    dav_client.assert_called_with(
        "https://example.com/url-2",
        username=TEST_USERNAME,
        password="password-2",
        ssl_verify_cert=False,
        timeout=ANY,
    )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert dict(config_entry.data) == {
        CONF_URL: "https://example.com/url-2",
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: "password-2",
        CONF_VERIFY_SSL: False,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (Exception(), "unknown"),
        (caldav_requests.exceptions.Timeout(), "cannot_connect"),
        (caldav_requests.exceptions.ConnectionError(), "cannot_connect"),
        (DAVError(), "cannot_connect"),
        (AuthorizationError(reason="Unauthorized"), "invalid_auth"),
        (AuthorizationError(reason="Other"), "cannot_connect"),
    ],
)
async def test_reconfigure_failure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    config_entry: MockConfigEntry,
    dav_client: Mock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test a failure during reconfiguration and recovering from it."""

    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)

    dav_client.return_value.get_principal.side_effect = side_effect

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: TEST_URL,
            CONF_PASSWORD: "password-2",
        },
    )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("errors") == {"base": expected_error}

    dav_client.return_value.get_principal.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: TEST_URL,
            CONF_PASSWORD: "password-3",
        },
    )
    await hass.async_block_till_done()

    assert result3.get("type") is FlowResultType.ABORT
    assert result3.get("reason") == "reconfigure_successful"

    assert dict(config_entry.data) == {
        CONF_URL: TEST_URL,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: "password-3",
        CONF_VERIFY_SSL: True,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_duplicate(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring to the server and account of another entry."""

    config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        data={**config_entry.data, CONF_URL: "https://example.com/url-2"},
    ).add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://example.com/url-2",
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "already_configured"
    assert config_entry.data[CONF_URL] == TEST_URL


@pytest.mark.parametrize(
    ("user_input"),
    [
        {
            CONF_URL: f"{TEST_URL}/different-path",
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
        {
            CONF_URL: TEST_URL,
            CONF_USERNAME: f"{TEST_USERNAME}-different-user",
            CONF_PASSWORD: TEST_PASSWORD,
        },
    ],
)
async def test_multiple_config_entries(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    config_entry: MockConfigEntry,
    user_input: dict[str, str],
) -> None:
    """Test multiple configuration entries with unique settings."""

    config_entry.add_to_hass(hass)
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert not result.get("errors")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == user_input[CONF_USERNAME]
    assert result2.get("data") == {
        **user_input,
        CONF_VERIFY_SSL: True,
    }
    assert len(mock_setup_entry.mock_calls) == 2
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2


@pytest.mark.parametrize(
    ("user_input"),
    [
        {
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
        {
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: f"{TEST_PASSWORD}-different",
        },
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate_config_entries(
    hass: HomeAssistant, config_entry: MockConfigEntry, user_input: dict[str, str]
) -> None:
    """Test multiple configuration entries with the same settings."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert not result.get("errors")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "already_configured"
