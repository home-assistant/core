"""The tests for LG webOS TV repairs."""

from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.components.webostv.repairs import async_create_fix_flow
from homeassistant.components.webostv.triggers.turn_on import DEPRECATED_TARGET_ISSUE_ID
from homeassistant.core import HomeAssistant


async def test_async_create_fix_flow(hass: HomeAssistant) -> None:
    """Test the deprecated trigger target issue is fixable by confirmation."""
    flow = await async_create_fix_flow(hass, DEPRECATED_TARGET_ISSUE_ID, None)

    assert isinstance(flow, ConfirmRepairFlow)
