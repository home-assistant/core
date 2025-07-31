"""The sensor tests for the tado platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

CHILD_LOCK_SWITCH_ENTITY = "switch.baseboard_heater_child_lock"


@pytest.fixture(autouse=True)
def loaded_platforms():
    """Load the binary sensor platform for the tests."""
    with patch("homeassistant.components.tado.PLATFORMS", [Platform.SWITCH]):
        yield


async def trigger_update(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Trigger an update of the Tado integration.

    Since the binary sensor platform doesn't infer a state immediately without extra requests,
    so adding this here to remove in a follow-up PR.
    """
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_tado_api")
async def test_child_lock(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test creation of child lock entity."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)
    state = hass.states.get(CHILD_LOCK_SWITCH_ENTITY)
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("method", "expected"), [(SERVICE_TURN_ON, True), (SERVICE_TURN_OFF, False)]
)
async def test_set_child_lock(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tado_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
    method: str,
    expected: bool,
) -> None:
    """Test enable child lock on switch."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        method,
        {ATTR_ENTITY_ID: CHILD_LOCK_SWITCH_ENTITY},
        blocking=True,
    )

    mock_tado_api.set_child_lock.assert_called_once()
    assert mock_tado_api.set_child_lock.call_args[0][1] is expected
