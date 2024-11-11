"""Tests for the acaia buttons."""

from datetime import timedelta
from unittest.mock import MagicMock

from aioacaia.exceptions import AcaiaDeviceNotFound, AcaiaError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.acaia.const import DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import async_fire_time_changed

pytestmark = pytest.mark.usefixtures("init_integration")


BUTTONS = (
    "tare",
    "reset_timer",
    "start_stop_timer",
)


async def test_button_presses(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    mock_scale: MagicMock,
) -> None:
    """Test the acaia buttons."""

    device = device_registry.async_get_device({(DOMAIN, mock_scale.mac)})
    assert device
    assert device == snapshot(name="device")

    for button in BUTTONS:
        state = hass.states.get(f"button.lunar_ddeeff_{button}")
        assert state
        assert state == snapshot(name=f"state_button_{button}")

        entry = entity_registry.async_get(state.entity_id)
        assert entry
        assert entry == snapshot(name=f"entry_button_{button}")

        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: f"button.lunar_ddeeff_{button}",
            },
            blocking=True,
        )

        function = getattr(mock_scale, button)
        function.assert_called_once()


async def test_buttons_unavailable_on_disconnected_scale(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the acaia buttons are unavailable when the scale is disconnected."""

    for button in BUTTONS:
        state = hass.states.get(f"button.lunar_ddeeff_{button}")
        assert state
        assert state.state == STATE_UNKNOWN

    mock_scale.connected = False
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for button in BUTTONS:
        state = hass.states.get(f"button.lunar_ddeeff_{button}")
        assert state
        assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "exception", [AcaiaError, AcaiaDeviceNotFound("Boom"), TimeoutError]
)
async def test_buttons_unavailable_on_update_exception(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test the acaia buttons are unavailable when the scale throws an error on update."""
    mock_scale.connect.side_effect = exception
    mock_scale.connected = False

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_scale.device_disconnected_handler.assert_called_once()

    for button in BUTTONS:
        state = hass.states.get(f"button.lunar_ddeeff_{button}")
        assert state
        assert state.state == STATE_UNAVAILABLE
