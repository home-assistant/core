"""Tests for the DVLA config flow."""

from unittest.mock import AsyncMock

from aio_dvla_vehicle_enquiry import DVLAError, DVLAInvalidRegistrationError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.dvla.const import CONF_REG_NUMBER, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def assert_error_recovers(
    hass: HomeAssistant,
    mock_dvla_client: AsyncMock,
    error: Exception,
    error_key: str,
    invalid_reg_number: str = "INVALID",
) -> None:
    """Test a config flow error can recover with valid input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    mock_dvla_client.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_REG_NUMBER: invalid_reg_number},
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
        user_input={CONF_REG_NUMBER: "ab12 cde"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AB12CDE"
    assert result["data"] == {CONF_REG_NUMBER: "AB12CDE"}
    assert result["result"].unique_id == "AB12CDE"


async def test_form_invalid_registration_recovers(
    hass: HomeAssistant,
    mock_dvla_client: AsyncMock,
) -> None:
    """Test invalid registration error can recover."""
    await assert_error_recovers(
        hass,
        mock_dvla_client,
        DVLAInvalidRegistrationError("Invalid registration number"),
        "invalid_registration",
    )


async def test_form_cannot_connect_recovers(
    hass: HomeAssistant,
    mock_dvla_client: AsyncMock,
) -> None:
    """Test connection error can recover."""
    await assert_error_recovers(
        hass,
        mock_dvla_client,
        DVLAError("DVLA unavailable"),
        "cannot_connect",
        invalid_reg_number="AB12CDE",
    )


async def test_form_unknown_error_recovers(
    hass: HomeAssistant,
    mock_dvla_client: AsyncMock,
) -> None:
    """Test unknown error can recover."""
    await assert_error_recovers(
        hass,
        mock_dvla_client,
        Exception("Unexpected error"),
        "unknown",
        invalid_reg_number="AB12CDE",
    )


async def test_form_vehicle_not_found_recovers(
    hass: HomeAssistant,
    mock_dvla_client: AsyncMock,
) -> None:
    """Test vehicle not found error can recover."""
    await assert_error_recovers(
        hass,
        mock_dvla_client,
        DVLAInvalidRegistrationError("Vehicle not found"),
        "invalid_registration",
        invalid_reg_number="UNKNOWN",
    )
