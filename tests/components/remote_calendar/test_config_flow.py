"""Test the Remote Calendar config flow."""

from httpx import HTTPError, InvalidURL, Response, TimeoutException
import pytest
import respx

from homeassistant.components.remote_calendar.const import CONF_CALENDAR_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import CALENDAR_NAME, CALENDER_URL

from tests.common import MockConfigEntry, get_schema_suggested_value


@respx.mock
async def test_form_import_ics(hass: HomeAssistant, ics_content: str) -> None:
    """Test we get the import form."""
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=ics_content,
        )
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_CALENDAR_NAME: CALENDAR_NAME,
            CONF_URL: CALENDER_URL,
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == CALENDAR_NAME
    assert result2["data"] == {
        CONF_CALENDAR_NAME: CALENDAR_NAME,
        CONF_URL: CALENDER_URL,
    }


@respx.mock
async def test_form_import_webcal(hass: HomeAssistant, ics_content: str) -> None:
    """Test we get the import form."""
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=ics_content,
        )
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_CALENDAR_NAME: CALENDAR_NAME,
            CONF_URL: "webcal://some.calendar.com/calendar.ics",
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == CALENDAR_NAME
    assert result2["data"] == {
        CONF_CALENDAR_NAME: CALENDAR_NAME,
        CONF_URL: CALENDER_URL,
    }


@pytest.mark.parametrize(
    ("side_effect", "base_error"),
    [
        (TimeoutException("Connection timed out"), "timeout_connect"),
        (HTTPError("Connection failed"), "cannot_connect"),
        (InvalidURL("Unsupported protocol"), "cannot_connect"),
    ],
)
@respx.mock
async def test_form_invalid_url(
    hass: HomeAssistant,
    side_effect: Exception,
    ics_content: str,
    base_error: str,
) -> None:
    """Test we get the import form with preserved fields on error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    respx.get("invalid-url.com").mock(side_effect=side_effect)

    user_input = {
        CONF_CALENDAR_NAME: CALENDAR_NAME,
        CONF_URL: "invalid-url.com",
    }
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": base_error}
    # Verify fields are preserved
    assert (
        get_schema_suggested_value(result2["data_schema"], CONF_CALENDAR_NAME)
        == CALENDAR_NAME
    )
    assert (
        get_schema_suggested_value(result2["data_schema"], CONF_URL)
        == "invalid-url.com"
    )
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=ics_content,
        )
    )
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CALENDAR_NAME: CALENDAR_NAME,
            CONF_URL: CALENDER_URL,
        },
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == CALENDAR_NAME
    assert result3["data"] == {
        CONF_CALENDAR_NAME: CALENDAR_NAME,
        CONF_URL: CALENDER_URL,
    }


@pytest.mark.parametrize(
    ("url", "log_message"),
    [
        (
            "unsupported://protocol.com",  # Test for httpx.UnsupportedProtocol
            "Request URL has an unsupported protocol 'unsupported://'",
        ),
        (
            "invalid-url",  # Test for httpx.ProtocolError
            "Request URL is missing an 'http://' or 'https://' protocol",
        ),
        (
            "https://example.com:abc/",  # Test for httpx.InvalidURL
            "Invalid port: 'abc'",
        ),
    ],
)
async def test_unsupported_inputs(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, url: str, log_message: str
) -> None:
    """Test that an unsupported inputs results in a form error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CALENDAR_NAME: CALENDAR_NAME,
            CONF_URL: url,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    assert log_message in caplog.text
    ## It's not possible to test a successful config flow because, we need to mock httpx.get here
    ## and then the exception isn't raised anymore.


@respx.mock
async def test_form_http_status_forbidden(
    hass: HomeAssistant, ics_content: str
) -> None:
    """Test 403 Forbidden shows error with preserved fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=403,
        )
    )

    user_input = {
        CONF_CALENDAR_NAME: CALENDAR_NAME,
        CONF_URL: CALENDER_URL,
    }
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "forbidden"}
    # Verify fields are preserved
    assert (
        get_schema_suggested_value(result2["data_schema"], CONF_CALENDAR_NAME)
        == CALENDAR_NAME
    )
    assert get_schema_suggested_value(result2["data_schema"], CONF_URL) == CALENDER_URL

    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=ics_content,
        )
    )
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == CALENDAR_NAME
    assert result3["data"] == {
        CONF_CALENDAR_NAME: CALENDAR_NAME,
        CONF_URL: CALENDER_URL,
    }


@respx.mock
async def test_form_http_status_unauthorized_auth_flow(
    hass: HomeAssistant, ics_content: str
) -> None:
    """Test 401 Unauthorized triggers auth flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=401,
        )
    )

    user_input = {
        CONF_CALENDAR_NAME: CALENDAR_NAME,
        CONF_URL: CALENDER_URL,
    }
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "auth"

    # Test auth step with wrong credentials
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=401,
        )
    )
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "wrong_user",
            CONF_PASSWORD: "wrong_pass",
        },
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "auth"
    assert result3["errors"] == {"base": "unauthorized"}
    # Verify auth fields are preserved
    assert (
        get_schema_suggested_value(result3["data_schema"], CONF_USERNAME)
        == "wrong_user"
    )
    assert (
        get_schema_suggested_value(result3["data_schema"], CONF_PASSWORD)
        == "wrong_pass"
    )

    # Test auth step with correct credentials but invalid ICS
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text="invalid ics content",
        )
    )
    result4 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_pass",
        },
    )
    assert result4["type"] is FlowResultType.FORM
    assert result4["step_id"] == "auth"
    assert result4["errors"] == {"base": "invalid_ics_file"}

    # Now test with valid ICS to complete the flow
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=ics_content,
        )
    )
    result5 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_pass",
        },
    )
    assert result5["type"] is FlowResultType.CREATE_ENTRY
    assert result5["title"] == CALENDAR_NAME
    assert result5["data"] == {
        CONF_CALENDAR_NAME: CALENDAR_NAME,
        CONF_URL: CALENDER_URL,
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
    }


@respx.mock
async def test_form_auth_http_status_forbidden(
    hass: HomeAssistant, ics_content: str
) -> None:
    """Test 403 Forbidden in auth step shows error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=401,
        )
    )

    user_input = {
        CONF_CALENDAR_NAME: CALENDAR_NAME,
        CONF_URL: CALENDER_URL,
    }
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "auth"

    # Test auth step with 403 forbidden
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=403,
        )
    )
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_pass",
        },
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "auth"
    assert result3["errors"] == {"base": "forbidden"}
    # Verify auth fields are preserved
    assert (
        get_schema_suggested_value(result3["data_schema"], CONF_USERNAME) == "test_user"
    )
    assert (
        get_schema_suggested_value(result3["data_schema"], CONF_PASSWORD) == "test_pass"
    )


@pytest.mark.parametrize(
    ("side_effect", "base_error"),
    [
        (TimeoutException("Connection timed out"), "timeout_connect"),
        (HTTPError("Connection failed"), "cannot_connect"),
    ],
)
@respx.mock
async def test_form_auth_connection_errors(
    hass: HomeAssistant,
    side_effect: Exception,
    base_error: str,
    ics_content: str,
) -> None:
    """Test connection errors in auth step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=401,
        )
    )

    user_input = {
        CONF_CALENDAR_NAME: CALENDAR_NAME,
        CONF_URL: CALENDER_URL,
    }
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "auth"

    # Test auth step with connection error
    respx.get(CALENDER_URL).mock(side_effect=side_effect)
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_pass",
        },
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "auth"
    assert result3["errors"] == {"base": base_error}


@respx.mock
async def test_no_valid_calendar(hass: HomeAssistant, ics_content: str) -> None:
    """Test invalid ics content with preserved fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text="blabla",
        )
    )

    user_input = {
        CONF_CALENDAR_NAME: CALENDAR_NAME,
        CONF_URL: CALENDER_URL,
    }
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_ics_file"}
    # Verify fields are preserved
    assert (
        get_schema_suggested_value(result2["data_schema"], CONF_CALENDAR_NAME)
        == CALENDAR_NAME
    )
    assert get_schema_suggested_value(result2["data_schema"], CONF_URL) == CALENDER_URL
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=200,
            text=ics_content,
        )
    )
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CALENDAR_NAME: CALENDAR_NAME,
            CONF_URL: CALENDER_URL,
        },
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == CALENDAR_NAME
    assert result3["data"] == {
        CONF_CALENDAR_NAME: CALENDAR_NAME,
        CONF_URL: CALENDER_URL,
    }


async def test_duplicate_name(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test two calendars cannot be added with the same name."""

    await setup_integration(hass, config_entry)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result.get("errors")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CALENDAR_NAME: CALENDAR_NAME,
            CONF_URL: "http://other-calendar.com",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@respx.mock
async def test_form_with_api_key_in_url(hass: HomeAssistant, ics_content: str) -> None:
    """Test calendar URL with API key parameter gets processed correctly."""
    api_key_url = f"{CALENDER_URL}?apikey=test_api_key"
    respx.get(api_key_url).mock(
        return_value=Response(
            status_code=200,
            text=ics_content,
        )
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CALENDAR_NAME: CALENDAR_NAME,
            CONF_URL: api_key_url,
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == CALENDAR_NAME
    assert result2["data"] == {
        CONF_CALENDAR_NAME: CALENDAR_NAME,
        CONF_URL: api_key_url,
    }


async def test_duplicate_url(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test two calendars cannot be added with the same url."""

    await setup_integration(hass, config_entry)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result.get("errors")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CALENDAR_NAME: "new name",
            CONF_URL: CALENDER_URL,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
