"""Tests for phone-number normalization (E.164) in the config flow."""

from __future__ import annotations

from httpx import Response
import pytest
import respx

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.noonlight.config_flow import (
    normalize_phone,
    normalize_state,
    normalize_zip,
)
from homeassistant.components.noonlight.const import (
    CONF_API_TOKEN,
    CONF_ENVIRONMENT,
    CONF_NAME,
    CONF_PHONE,
    CONF_STATE,
    CONF_ZIP,
    DOMAIN,
    ENV_SANDBOX,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2025550142", "+12025550142"),
        ("(202) 555-0142", "+12025550142"),
        ("202-555-0142", "+12025550142"),
        ("202.555.0142", "+12025550142"),
        ("12025550142", "+12025550142"),
        ("+12025550142", "+12025550142"),
        ("+1 (202) 555-0142", "+12025550142"),
        ("+44 20 7946 0958", "+442079460958"),
    ],
)
def test_normalize_phone_valid(raw, expected):
    """Valid phone numbers normalize to the expected E.164 form."""
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "123", "abcdefghij", "55512345", "+1", "00000000000000000000"],
)
def test_normalize_phone_invalid(raw):
    """Invalid phone numbers raise ValueError."""
    with pytest.raises(ValueError):
        normalize_phone(raw)


@respx.mock
async def test_caller_step_normalizes_phone(hass):
    """A bare 10-digit number is stored as E.164 on the created entry."""
    respx.route(method="GET", url__regex=r".*/status").mock(return_value=Response(404))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "tok", CONF_ENVIRONMENT: ENV_SANDBOX},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Main",
            CONF_PHONE: "(202) 555-0142",
            "address": "1 Test St",
            "city": "Testville",
            "state": "CA",
            "zip": "90001",
        },
    )
    assert result["step_id"] == "defaults"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "default_entry_delay_seconds": 30,
            "dedupe_seconds": 300,
            "services_granted": ["police"],
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PHONE] == "+12025550142"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("va", "VA"), ("VA", "VA"), (" ca ", "CA"), ("Ny", "NY"), ("dc", "DC")],
)
def test_normalize_state_valid(raw, expected):
    """Valid states normalize to the expected uppercase abbreviation."""
    assert normalize_state(raw) == expected


@pytest.mark.parametrize("raw", ["", "Virginia", "v", "XX", "USA", "123"])
def test_normalize_state_invalid(raw):
    """Invalid states raise ValueError."""
    with pytest.raises(ValueError):
        normalize_state(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("62704", "62704"), ("62704-1234", "62704-1234"), (" 90001 ", "90001")],
)
def test_normalize_zip_valid(raw, expected):
    """Valid ZIP codes normalize to the expected form."""
    assert normalize_zip(raw) == expected


@pytest.mark.parametrize("raw", ["", "1234", "abcde", "627040", "2221-1234"])
def test_normalize_zip_invalid(raw):
    """Invalid ZIP codes raise ValueError."""
    with pytest.raises(ValueError):
        normalize_zip(raw)


async def _submit_caller(hass, caller):
    """Run the user step then submit the given caller dict; return the result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "tok", CONF_ENVIRONMENT: ENV_SANDBOX},
    )
    return await hass.config_entries.flow.async_configure(result["flow_id"], caller)


@respx.mock
async def test_caller_step_reports_all_errors_at_once(hass):
    """Bad phone + state + ZIP all surface together, not one at a time."""
    respx.route(method="GET", url__regex=r".*/status").mock(return_value=Response(404))
    result = await _submit_caller(
        hass,
        {
            CONF_NAME: "Main",
            CONF_PHONE: "123",
            "address": "1 Test St",
            "city": "Testville",
            CONF_STATE: "Virginia",
            CONF_ZIP: "abc",
        },
    )
    assert result["step_id"] == "caller"
    assert result["errors"][CONF_PHONE] == "invalid_phone"
    assert result["errors"][CONF_STATE] == "invalid_state"
    assert result["errors"][CONF_ZIP] == "invalid_zip"


@respx.mock
async def test_caller_step_rejects_bad_phone(hass):
    """An invalid phone in the caller step surfaces an invalid_phone error."""
    respx.route(method="GET", url__regex=r".*/status").mock(return_value=Response(404))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "tok", CONF_ENVIRONMENT: ENV_SANDBOX},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Main",
            CONF_PHONE: "123",
            "address": "1 Test St",
            "city": "Testville",
            "state": "CA",
            "zip": "90001",
        },
    )
    assert result["step_id"] == "caller"
    assert result["errors"][CONF_PHONE] == "invalid_phone"
