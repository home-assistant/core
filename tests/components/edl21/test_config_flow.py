"""Test EDL21 config flow."""

import pytest

from homeassistant.components.edl21.const import CONF_SERIAL_PORT, DEFAULT_TITLE, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

VALID_CONFIG = {CONF_SERIAL_PORT: "/dev/ttyUSB1"}
VALID_LEGACY_CONFIG = {CONF_NAME: "My Smart Meter", CONF_SERIAL_PORT: "/dev/ttyUSB1"}

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        VALID_CONFIG,
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_TITLE
    assert result["data"][CONF_SERIAL_PORT] == VALID_CONFIG[CONF_SERIAL_PORT]


async def test_integration_already_exists(hass: HomeAssistant) -> None:
    """Test that a new entry must not have the same serial port as an existing entry."""

    MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=VALID_CONFIG,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_create_entry_by_import(hass: HomeAssistant) -> None:
    """Test that the import step works."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=VALID_LEGACY_CONFIG,
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == VALID_LEGACY_CONFIG[CONF_NAME]
    assert result["data"][CONF_NAME] == VALID_LEGACY_CONFIG[CONF_NAME]
    assert result["data"][CONF_SERIAL_PORT] == VALID_LEGACY_CONFIG[CONF_SERIAL_PORT]

    # Test the import step with an empty string as name
    # (the name is optional in the old schema and defaults to "")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_SERIAL_PORT: "/dev/ttyUSB2", CONF_NAME: ""},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_TITLE
    assert result["data"][CONF_NAME] == ""
    assert result["data"][CONF_SERIAL_PORT] == "/dev/ttyUSB2"
