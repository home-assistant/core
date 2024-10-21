"""Test GPM repairs."""

from homeassistant.components.gpm import repairs
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from tests.common import async_capture_events


async def test_create_fix_flow_none(hass: HomeAssistant) -> None:
    """Test async_create_fix_flow returns None on unknown issue_id."""

    assert (await repairs.async_create_fix_flow(hass, "unknown", None)) is None


async def test_restart_required_fix_flow(hass: HomeAssistant) -> None:
    """Test RestartRequiredFixFlow steps."""
    # homeassistant is needed to test restarting
    assert await async_setup_component(hass, "homeassistant", {})

    fix_flow = await repairs.async_create_fix_flow(hass, "restart_required.foobar", {})
    fix_flow.hass = hass

    result = await fix_flow.async_step_init()
    assert result["type"] == FlowResultType.MENU

    events = async_capture_events(hass, "call_service")
    result = await fix_flow.async_step_restart()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert len(events) == 1
    assert events[0].data["domain"] == "homeassistant"
    assert events[0].data["service"] == "restart"
