"""Tests for the DVLA config flow."""

from unittest.mock import patch

from aio_dvla_vehicle_enquiry import DVLAError, DVLAInvalidRegistrationError

from homeassistant import config_entries
from homeassistant.components.dvla.const import CONF_REG_NUMBER, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def assert_error_recovers(
    hass: HomeAssistant,
    error: Exception,
    error_key: str,
    invalid_reg_number: str = "INVALID",
) -> None:
    """Test a config flow error can recover with valid input."""
    with patch(
        "homeassistant.components.dvla.config_flow.DVLAClient.async_get_vehicle",
        side_effect=[
            error,
            {"registrationNumber": "AB12CDE"},
            {"registrationNumber": "AB12CDE"},
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_REG_NUMBER: invalid_reg_number},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": error_key}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_REG_NUMBER: "AB12CDE"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AB12CDE"
    assert result["data"] == {CONF_REG_NUMBER: "AB12CDE"}


async def test_form(hass: HomeAssistant) -> None:
    """Test that the form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test that an already configured vehicle aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="AB12CDE",
        unique_id="AB12CDE",
        data={
            CONF_REG_NUMBER: "AB12CDE",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_REG_NUMBER: "ab12 cde",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_success(hass: HomeAssistant) -> None:
    """Test successful config flow."""
    with patch(
        "homeassistant.components.dvla.config_flow.DVLAClient.async_get_vehicle",
        return_value={"registrationNumber": "AB12CDE"},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_REG_NUMBER: "AB12CDE"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AB12CDE"
    assert result["data"] == {CONF_REG_NUMBER: "AB12CDE"}


async def test_form_invalid_registration_recovers(hass: HomeAssistant) -> None:
    """Test invalid registration error can recover."""
    await assert_error_recovers(
        hass,
        DVLAInvalidRegistrationError("Invalid registration number"),
        "invalid_registration",
    )


async def test_form_cannot_connect_recovers(hass: HomeAssistant) -> None:
    """Test connection error can recover."""
    await assert_error_recovers(
        hass,
        DVLAError("DVLA unavailable"),
        "cannot_connect",
        invalid_reg_number="AB12CDE",
    )


async def test_form_unknown_error_recovers(hass: HomeAssistant) -> None:
    """Test unknown error can recover."""
    await assert_error_recovers(
        hass,
        Exception("Unexpected error"),
        "unknown",
        invalid_reg_number="AB12CDE",
    )


async def test_form_vehicle_not_found_recovers(hass: HomeAssistant) -> None:
    """Test vehicle not found error can recover."""
    await assert_error_recovers(
        hass,
        DVLAInvalidRegistrationError("Vehicle not found"),
        "invalid_registration",
        invalid_reg_number="UNKNOWN",
    )
