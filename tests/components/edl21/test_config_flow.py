"""Test EDL21 config flow."""

from homeassistant import data_entry_flow
from homeassistant.components.edl21.const import (
    CONF_SERIAL_PORT,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME

from tests.common import MockConfigEntry

VALID_CONFIG = {CONF_NAME: "My Smart Meter", CONF_SERIAL_PORT: "/dev/ttyUSB1"}


async def test_show_form(hass) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER


async def test_integration_already_exists(hass) -> None:
    """Test that a new entry must not have the same name or serial port as an existing entry."""

    MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=VALID_CONFIG,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_NAME: "Other Smart Meter",
            CONF_SERIAL_PORT: VALID_CONFIG.get(CONF_SERIAL_PORT),
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_NAME: VALID_CONFIG.get(CONF_NAME), CONF_SERIAL_PORT: "/dev/ttyUSB2"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_create_entry_by_user(hass) -> None:
    """Test that the user step works."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=VALID_CONFIG,
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == VALID_CONFIG.get(CONF_NAME)
    assert result["data"][CONF_NAME] == VALID_CONFIG.get(CONF_NAME)
    assert result["data"][CONF_SERIAL_PORT] == VALID_CONFIG.get(CONF_SERIAL_PORT)


async def test_create_entry_by_import(hass) -> None:
    """Test that the import step works."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=VALID_CONFIG,
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == VALID_CONFIG.get(CONF_NAME)
    assert result["data"][CONF_NAME] == VALID_CONFIG.get(CONF_NAME)
    assert result["data"][CONF_SERIAL_PORT] == VALID_CONFIG.get(CONF_SERIAL_PORT)

    # Test the import step with an empty string as name (the name is optional in the old schema and defaults to "")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_SERIAL_PORT: "/dev/ttyUSB2", CONF_NAME: ""},
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_DEVICE_NAME
    assert result["data"][CONF_NAME] == ""
    assert result["data"][CONF_SERIAL_PORT] == "/dev/ttyUSB2"
