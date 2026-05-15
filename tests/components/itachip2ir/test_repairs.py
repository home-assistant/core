"""Tests for iTach IP2IR repairs."""

from homeassistant.components.itachip2ir.const import DOMAIN
from homeassistant.components.itachip2ir.repairs import (
    ISSUE_CANNOT_CONNECT,
    ISSUE_INVALID_CONFIG,
    ISSUE_NO_IR_PORTS,
    ReconfigureRepairFlow,
    async_create_fix_flow,
    async_create_repair_issue,
    async_delete_repair_issue,
)
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir


async def test_create_repair_issue(hass: HomeAssistant) -> None:
    """Test creating a repair issue."""
    async_create_repair_issue(
        hass,
        ISSUE_CANNOT_CONNECT,
        translation_key="cannot_connect",
        placeholders={
            "entry_title": "iTach IP2IR",
            "host": "192.168.1.211",
        },
    )

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_CANNOT_CONNECT)

    assert issue is not None
    assert issue.domain == DOMAIN
    assert issue.issue_id == ISSUE_CANNOT_CONNECT
    assert issue.issue_domain == DOMAIN
    assert issue.is_fixable is False
    assert issue.is_persistent is False
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.translation_key == "cannot_connect"
    assert issue.translation_placeholders == {
        "entry_title": "iTach IP2IR",
        "host": "192.168.1.211",
    }


async def test_create_repair_issue_explicitly_fixable(hass: HomeAssistant) -> None:
    """Test creating an explicitly fixable repair issue."""
    async_create_repair_issue(
        hass,
        ISSUE_INVALID_CONFIG,
        translation_key="invalid_config",
        is_fixable=True,
    )

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_INVALID_CONFIG)

    assert issue is not None
    assert issue.is_fixable is True
    assert issue.translation_key == "invalid_config"
    assert issue.translation_placeholders is None


async def test_delete_repair_issue(hass: HomeAssistant) -> None:
    """Test deleting a repair issue."""
    async_create_repair_issue(
        hass,
        ISSUE_NO_IR_PORTS,
        translation_key="no_ir_ports",
    )

    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_NO_IR_PORTS) is not None

    async_delete_repair_issue(hass, ISSUE_NO_IR_PORTS)

    assert issue_registry.async_get_issue(DOMAIN, ISSUE_NO_IR_PORTS) is None


async def test_delete_missing_repair_issue(hass: HomeAssistant) -> None:
    """Test deleting a missing repair issue is harmless."""
    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_CANNOT_CONNECT) is None

    async_delete_repair_issue(hass, ISSUE_CANNOT_CONNECT)

    assert issue_registry.async_get_issue(DOMAIN, ISSUE_CANNOT_CONNECT) is None


async def test_async_create_fix_flow_returns_reconfigure_repair_flow(
    hass: HomeAssistant,
) -> None:
    """Test fix flow factory returns the expected flow."""
    flow = await async_create_fix_flow(
        hass,
        ISSUE_CANNOT_CONNECT,
        {
            "entry_title": "Living Room iTach",
            "host": "192.168.1.211",
        },
    )

    assert isinstance(flow, ReconfigureRepairFlow)
    assert isinstance(flow, RepairsFlow)


async def test_reconfigure_repair_flow_init_shows_confirm_form(
    hass: HomeAssistant,
) -> None:
    """Test repair flow init step shows the confirm form."""
    flow = ReconfigureRepairFlow(
        ISSUE_CANNOT_CONNECT,
        {
            "entry_title": "Living Room iTach",
            "host": "192.168.1.211",
        },
    )
    flow.hass = hass

    result = await flow.async_step_init()

    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "entry_title": "Living Room iTach",
        "host": "192.168.1.211",
    }


async def test_reconfigure_repair_flow_confirm_uses_default_placeholders(
    hass: HomeAssistant,
) -> None:
    """Test repair flow confirm step falls back to default placeholders."""
    flow = ReconfigureRepairFlow(ISSUE_INVALID_CONFIG, None)
    flow.hass = hass

    result = await flow.async_step_confirm()

    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "entry_title": "iTach IP2IR",
        "host": "unknown",
    }


async def test_reconfigure_repair_flow_submit_deletes_issue(
    hass: HomeAssistant,
) -> None:
    """Test submitting the repair flow deletes the repair issue."""
    async_create_repair_issue(
        hass,
        ISSUE_CANNOT_CONNECT,
        translation_key="cannot_connect",
    )

    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_CANNOT_CONNECT) is not None

    flow = ReconfigureRepairFlow(ISSUE_CANNOT_CONNECT, None)
    flow.hass = hass

    result = await flow.async_step_confirm({})

    assert result["type"] == "create_entry"
    assert result["title"] == ""
    assert result["data"] == {}
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_CANNOT_CONNECT) is None
