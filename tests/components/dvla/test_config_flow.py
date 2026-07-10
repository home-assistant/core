"""Tests for the DVLA config flow."""

from unittest.mock import patch

from voluptuous import raises

from homeassistant import config_entries
from homeassistant.components.dvla.config_flow import (
    CannotConnect,
    InvalidAuth,
    validate_input,
)
from homeassistant.components.dvla.const import CONF_REG_NUMBER, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test that the form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test creating an entry from user input."""
    with (
        patch(
            "homeassistant.components.dvla.config_flow.validate_input",
            return_value={"title": "AB12CDE"},
        ),
        patch(
            "homeassistant.components.dvla.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_REG_NUMBER: "AB12CDE",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AB12CDE"
    assert result["data"][CONF_REG_NUMBER] == "AB12CDE"

    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


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


async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid auth error."""
    with patch(
        "homeassistant.components.dvla.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_REG_NUMBER: "AB12CDE",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_unknown_error(hass: HomeAssistant) -> None:
    """Test unknown error."""
    with patch(
        "homeassistant.components.dvla.config_flow.validate_input",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_REG_NUMBER: "AB12CDE",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_validate_input_success(hass: HomeAssistant) -> None:
    """Test validate_input returns config entry title."""
    with patch(
        "homeassistant.components.dvla.config_flow.DVLACoordinator._async_update_data",
        return_value={"registrationNumber": "AB12CDE"},
    ):
        result = await validate_input(hass, {CONF_REG_NUMBER: "AB12CDE"})

    assert result == {"title": "AB12CDE"}


async def test_validate_input_invalid_auth(hass: HomeAssistant) -> None:
    """Test validate_input maps auth failures."""
    with (
        patch(
            "homeassistant.components.dvla.config_flow.DVLACoordinator._async_update_data",
            side_effect=ConfigEntryAuthFailed,
        ),
        raises(InvalidAuth),
    ):
        await validate_input(hass, {CONF_REG_NUMBER: "AB12CDE"})


async def test_validate_input_cannot_connect(hass: HomeAssistant) -> None:
    """Test validate_input maps update failures."""
    with (
        patch(
            "homeassistant.components.dvla.config_flow.DVLACoordinator._async_update_data",
            side_effect=UpdateFailed("boom"),
        ),
        raises(CannotConnect),
    ):
        await validate_input(hass, {CONF_REG_NUMBER: "AB12CDE"})


async def test_cannot_connect(hass: HomeAssistant) -> None:
    """Test cannot connect error."""
    with patch(
        "homeassistant.components.dvla.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_REG_NUMBER: "AB12CDE"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}
