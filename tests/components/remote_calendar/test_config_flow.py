"""Test the Remote Calendar config flow."""

from httpx import ConnectError, Response, UnsupportedProtocol
import pytest
import respx

from homeassistant.components.remote_calendar.const import (
    CONF_CALENDAR_NAME,
    CONF_MIDNIGHT_AS_ALL_DAY,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import CALENDAR_NAME, CALENDER_URL

from tests.common import MockConfigEntry


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
    ("side_effect"),
    [
        ConnectError("Connection failed"),
        UnsupportedProtocol("Unsupported protocol"),
    ],
)
@respx.mock
async def test_form_inavild_url(
    hass: HomeAssistant,
    side_effect: Exception,
    ics_content: str,
) -> None:
    """Test we get the import form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    respx.get("invalid-url.com").mock(side_effect=side_effect)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CALENDAR_NAME: CALENDAR_NAME,
            CONF_URL: "invalid-url.com",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
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


@pytest.mark.parametrize(
    ("http_status", "error"),
    [
        (401, "cannot_connect"),
        (403, "forbidden"),
    ],
)
@respx.mock
async def test_form_http_status_error(
    hass: HomeAssistant, ics_content: str, http_status: int, error: str
) -> None:
    """Test we http status."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    respx.get(CALENDER_URL).mock(
        return_value=Response(
            status_code=http_status,
        )
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CALENDAR_NAME: CALENDAR_NAME,
            CONF_URL: CALENDER_URL,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}
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


@respx.mock
async def test_no_valid_calendar(hass: HomeAssistant, ics_content: str) -> None:
    """Test invalid ics content."""
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

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_CALENDAR_NAME: CALENDAR_NAME,
            CONF_URL: CALENDER_URL,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_ics_file"}
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


async def test_options_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test the options flow form."""

    await setup_integration(hass, config_entry)

    # Test show Options form
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Test option is set
    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, data={CONF_MIDNIGHT_AS_ALL_DAY: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_MIDNIGHT_AS_ALL_DAY: True}
