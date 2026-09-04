"""Tests for repairs issue_handler.py."""

import pytest

from homeassistant.components.repairs import (
    DOMAIN,
    RepairsFlow,
    RepairsFlowResult,
    repairs_flow_manager,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.issue_registry as ir

from tests.common import AsyncMock, Mock, async_setup_component, mock_platform


@pytest.fixture(autouse=True)
async def mock_repairs_integration(hass: HomeAssistant) -> None:
    """Mock a repairs integration."""
    hass.config.components.add("fake_integration")

    def async_create_fix_flow(
        hass: HomeAssistant,
        issue_id: str,
        data: dict[str, str | int | float | None] | None,
    ) -> RepairsFlow:
        return MockFixFlowContext()

    mock_platform(
        hass,
        "fake_integration.repairs",
        Mock(async_create_fix_flow=AsyncMock(wraps=async_create_fix_flow)),
    )


class MockFixFlowContext(RepairsFlow):
    """Mock for context tests."""

    def __init__(self) -> None:
        """Initialize a MockFlowFixContext."""
        self.issue_id = "fake_issue"
        assert self.issue_id == "fake_issue"

    async def async_step_init(self, user_input: dict | None) -> RepairsFlowResult:
        """Initial step of a repairs flow."""
        return self.async_show_form()


@pytest.mark.parametrize(
    ("ignore_translations_for_mock_domains"),
    [
        ["fake_integration"],
    ],
)
async def test_flow_fix_via_data(hass: HomeAssistant) -> None:
    """Test that a repairs flow's issue_id can be set via data."""

    assert await async_setup_component(hass, DOMAIN, {})

    ir.async_create_issue(
        hass,
        issue_id="context_issue",
        domain="fake_integration",
        is_fixable=True,
        severity="error",
        translation_key="fake_key",
    )

    assert (repairs := repairs_flow_manager(hass))

    result = await repairs.async_init(
        "fake_integration", data={"issue_id": "context_issue"}
    )
    assert result["type"] == "form"
    result = repairs.async_get(result["flow_id"])
    assert result["context"] == {"issue_id": "context_issue"}


@pytest.mark.parametrize(
    ("ignore_translations_for_mock_domains"),
    [
        ["fake_integration"],
    ],
)
async def test_flow_fix_missing_context(hass: HomeAssistant) -> None:
    """Test that KeyError is thrown when context and data is missing."""

    assert await async_setup_component(hass, DOMAIN, {})

    assert (repairs := repairs_flow_manager(hass))

    with pytest.raises(KeyError) as exi:
        await repairs.async_init("fake_integration")

    assert "issue_id was not set in context" in str(exi.value)
