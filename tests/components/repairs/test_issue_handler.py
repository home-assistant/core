"""Test issue_handler.py."""

from __future__ import annotations

import logging

import pytest

from homeassistant.components.repairs import (
    DOMAIN,
    RepairsFlowContext,
    RepairsFlowManager,
    async_get,
    repairs_flow_manager,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


@pytest.mark.parametrize("ignore_translations_for_mock_domains", ["fake_integration"])
async def test_async_init(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test async_create_flow using legacy issue_id.

    legacy:
        data = {"issue_id" = "test_issue"}
    updated:
        context = RepairsFlowContext(issue_id = "test_issue")
    """

    with caplog.at_level(logging.WARNING):
        assert await async_setup_component(hass, DOMAIN, {})

        issue_registry: ir.IssueRegistry = ir.async_get(hass)
        issue_registry.async_get_or_create(
            "fake_integration",
            "fake_issue",
            is_persistent=False,
            is_fixable=TimeoutError,
            severity=ir.IssueSeverity.ERROR,
            translation_key="fake_issue",
        )

        rfm: RepairsFlowManager = async_get(hass)
        flow = await rfm.async_init("fake_integration", data={"issue_id": "fake_issue"})
        assert len(caplog.record_tuples) == 1
        _, _, msg = caplog.record_tuples[0]
        assert 'data={"issue_id": issue_id} instead of context' in msg
        rfm.async_abort(flow["flow_id"])
        caplog.clear()
        flow = await rfm.async_init(
            "fake_integration", context=RepairsFlowContext(issue_id="fake_issue")
        )
        assert not caplog.records


async def test_flow_manager_helper(hass: HomeAssistant) -> None:
    """Test accessing the repairs flow manager with the helper."""
    assert repairs_flow_manager(hass) is None

    with pytest.raises(PlatformNotReady):
        async_get(hass)

    assert await async_setup_component(hass, DOMAIN, {})

    flow_manager = repairs_flow_manager(hass)
    assert flow_manager is not None
    assert isinstance(flow_manager, RepairsFlowManager)
    flow_manager = async_get(hass)
    assert flow_manager is not None
    assert isinstance(flow_manager, RepairsFlowManager)
