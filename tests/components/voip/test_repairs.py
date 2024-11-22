"""Test VoIP repairs."""

import pytest

from homeassistant.components.voip import repairs
from homeassistant.core import HomeAssistant


async def test_create_fix_flow_raises_on_unknown_issue_id(hass: HomeAssistant) -> None:
    """Test reate_fix_flow raises on unknown issue_id."""

    with pytest.raises(ValueError):
        await repairs.async_create_fix_flow(hass, "no_such_issue", None)
