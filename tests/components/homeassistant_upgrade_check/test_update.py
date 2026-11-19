"""Tests for the mock core update of the Home Assistant Upgrade Check."""

import pytest

from homeassistant.components.homeassistant_upgrade_check.const import DOMAIN
from homeassistant.components.homeassistant_upgrade_check.mock import (
    MOCK_RUNNING,
    MOCK_TARGET,
)
from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

ENTITY_ID = "update.home_assistant_core_mock"


async def test_mock_core_update(hass: HomeAssistant) -> None:
    """Test the mock offers an upgrade but refuses to install it."""
    # Not the setup_integration fixture: that replaces the mock's versions.
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == MOCK_RUNNING
    assert state.attributes[ATTR_LATEST_VERSION] == MOCK_TARGET

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
    assert err.value.translation_key == "mock_install"
