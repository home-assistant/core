"""Test the Remote Calendar config flow."""

from httpx import ConnectError, Response, UnsupportedProtocol
import pytest
import respx

from homeassistant.components.remote_calendar.const import CONF_CALENDAR_NAME, DOMAIN
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


@pytest.mark.parametrize(
    "side_effect",
    [
        ConnectError("Connection failed"),
        UnsupportedProtocol("Unsupported protocol"),
        ValueError("Invalid response"),
    ],
)
@respx.mock
async def test_form_inavild_url(
    hass: HomeAssistant,
    side_effect: Exception,
) -> None:
    """Test we get the import form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    respx.get("http://invalid-url.com").mock(side_effect=side_effect)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CALENDAR_NAME: CALENDAR_NAME,
            CONF_URL: "http://invalid-url.com",
        },
    )
    assert result2["type"] is FlowResultType.FORM


@respx.mock
async def test_form_http_status_error(
    hass: HomeAssistant,
) -> None:
    """Test we http status."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    respx.get("http://invalid-url.com").mock(
        return_value=Response(
            status_code=403,
        )
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CALENDAR_NAME: CALENDAR_NAME,
            CONF_URL: "http://invalid-url.com",
        },
    )
    assert result2["type"] is FlowResultType.FORM


@respx.mock
async def test_no_valid_calendar(hass: HomeAssistant) -> None:
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
