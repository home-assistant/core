"""Tests for ActronAir Select Entity."""

from unittest.mock import AsyncMock

from homeassistant.components.actronair.const import DOMAIN
from homeassistant.components.actronair.select import ACSystemSelectEntity
from homeassistant.core import HomeAssistant


async def test_select_entity(hass: HomeAssistant) -> None:
    """Test AC system selector entity."""
    mock_coordinator = AsyncMock()
    entity = ACSystemSelectEntity(
        hass, mock_coordinator, mock_coordinator, None, "1234"
    )

    assert entity.name == "AC System Selector"
    assert entity._attr_unique_id == f"{DOMAIN}_ac_system_selector"
