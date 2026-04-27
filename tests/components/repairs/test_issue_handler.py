"""Test issue_handler.py."""

from __future__ import annotations

import pytest

from homeassistant.components.repairs import (
    DOMAIN,
    RepairsFlowManager,
    async_get,
    repairs_flow_manager,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.setup import async_setup_component


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
