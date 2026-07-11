"""Tests for the DVLA config flow."""

from unittest.mock import patch

from aio_dvla_vehicle_enquiry import DVLAError, DVLAInvalidRegistrationError

from homeassistant import config_entries
from homeassistant.components.dvla.const import CONF_REG_NUMBER, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


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


async def test_form_invalid_registration(hass: HomeAssistant) -> None:
    """Test invalid registration error."""
    with patch(
        "homeassistant.components.dvla.config_flow.DVLAClient.async_get_vehicle",
        side_effect=DVLAInvalidRegistrationError("Invalid registration number"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_REG_NUMBER: "INVALID"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_registration"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection error."""
    with patch(
        "homeassistant.components.dvla.config_flow.DVLAClient.async_get_vehicle",
        side_effect=DVLAError("DVLA unavailable"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_REG_NUMBER: "AB12CDE"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test unknown error."""
    with patch(
        "homeassistant.components.dvla.config_flow.DVLAClient.async_get_vehicle",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_REG_NUMBER: "AB12CDE"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_form_vehicle_not_found(hass: HomeAssistant) -> None:
    """Test vehicle not found maps to invalid registration."""
    with patch(
        "homeassistant.components.dvla.config_flow.DVLAClient.async_get_vehicle",
        side_effect=DVLAInvalidRegistrationError("Vehicle not found"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_REG_NUMBER: "UNKNOWN"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_registration"}
