"""Tests for the Debug console config flow."""

from homeassistant.components.debug_console.const import DOMAIN
from homeassistant.config_entries import SOURCE_SYSTEM, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test enabling the debug console after the warning."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Enabling it needs an explicit confirmation of the risks.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"accept_risks": False}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"accept_risks": "risks_not_accepted"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"accept_risks": True}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Debug console"
    assert result["data"] == {}


async def test_system_flow(hass: HomeAssistant) -> None:
    """Test development versions enable the debug console without asking."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SYSTEM}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Debug console"


async def test_single_instance(hass: HomeAssistant) -> None:
    """Test the debug console can only be enabled once."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
