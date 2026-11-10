"""Tests for the mock core update of the Home Assistant Upgrade Check."""

import pytest

from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

ENTITY_ID = "update.home_assistant_core_mock"


@pytest.mark.usefixtures("setup_integration")
async def test_mock_core_update(hass: HomeAssistant) -> None:
    """Test the mock offers an upgrade but refuses to install it."""
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2026.7.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "2026.11.0"

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
    assert err.value.translation_key == "mock_install"
