"""The sensor tests for the tado platform."""

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

from .util import async_init_integration

from tests.common import MockConfigEntry

CHILD_LOCK_SWITCH_ENTITY = "switch.baseboard_heater_child_lock"


@pytest.fixture(autouse=True)
def loaded_platforms():
    """Load the binary sensor platform for the tests."""
    with patch("homeassistant.components.tado.PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.mark.usefixtures("mock_tado_api")
async def test_child_lock(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test creation of child lock entity."""

    await async_init_integration(hass)
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

    await async_init_integration(hass)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        method,
        {ATTR_ENTITY_ID: CHILD_LOCK_SWITCH_ENTITY},
        blocking=True,
    )

    mock_tado_api.set_child_lock.assert_called_once()
    assert mock_tado_api.set_child_lock.call_args[0][1] is expected
