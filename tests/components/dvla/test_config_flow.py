"""Tests for the DVLA config flow."""

from unittest.mock import AsyncMock

from aio_dvla_vehicle_enquiry import (
    DVLAAuthError,
    DVLAError,
    DVLAInvalidRegistrationError,
    DVLARateLimitError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.dvla.const import CONF_REG_NUMBER, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test that the form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an already configured vehicle aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_REG_NUMBER: "ab12 cde"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_dvla_client")
async def test_form_success(hass: HomeAssistant) -> None:
    """Test successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_REG_NUMBER: " ab12\tcde\n"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AB12CDE"
    assert result["data"] == {CONF_REG_NUMBER: "AB12CDE"}
    assert result["result"].unique_id == "AB12CDE"


@pytest.mark.parametrize(
    "reg_number",
    [
        pytest.param("", id="empty"),
        pytest.param(" \t\n", id="whitespace"),
        pytest.param("AB12-CDE", id="punctuation"),
        pytest.param("AB12ß", id="non_ascii"),
    ],
)
async def test_form_rejects_malformed_registration(
    hass: HomeAssistant,
    mock_dvla_client: AsyncMock,
    reg_number: str,
) -> None:
    """Test malformed input never reaches DVLA or sets a unique ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_REG_NUMBER: reg_number},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_REG_NUMBER: "invalid_registration"}
    flow = hass.config_entries.flow.async_get(result["flow_id"])
    assert flow["context"].get("unique_id") is None
    mock_dvla_client.assert_not_called()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_REG_NUMBER: "AB12CDE"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "AB12CDE"


@pytest.mark.parametrize(
    ("error", "error_key"),
    [
        pytest.param(
            DVLAInvalidRegistrationError("Invalid registration number"),
            "invalid_registration",
            id="invalid_registration",
        ),
        pytest.param(
            DVLAInvalidRegistrationError("Vehicle not found"),
            "invalid_registration",
            id="vehicle_not_found",
        ),
        pytest.param(DVLAAuthError("Invalid key"), "auth_failed", id="auth"),
        pytest.param(
            DVLARateLimitError("Too many requests"), "rate_limited", id="rate"
        ),
        pytest.param(DVLAError("DVLA unavailable"), "cannot_connect", id="connection"),
        pytest.param(Exception("Unexpected error"), "unknown", id="unexpected"),
    ],
)
async def test_form_error_recovers(
    hass: HomeAssistant,
    mock_dvla_client: AsyncMock,
    error: Exception,
    error_key: str,
) -> None:
    """Test a config flow error can recover with a valid registration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    mock_dvla_client.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_REG_NUMBER: "UNKNOWN"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error_key}

    mock_dvla_client.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_REG_NUMBER: "AB12CDE"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AB12CDE"
    assert result["data"] == {CONF_REG_NUMBER: "AB12CDE"}
    assert result["result"].unique_id == "AB12CDE"
