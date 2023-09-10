"""Tests for HomematicIP Cloud button."""
from unittest.mock import patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button.const import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .helper import get_and_check_entity_basics


async def test_hmip_garage_door_controller_button(
    hass: HomeAssistant, default_mock_hap_factory
) -> None:
    """Test HomematicipGarageDoorControllerButton."""
    entity_id = "button.garagentor"
    entity_name = "Garagentor"
    device_model = "HmIP-WGC"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=[entity_name]
    )

    get_and_check_entity_basics(hass, mock_hap, entity_id, entity_name, device_model)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == now.isoformat()
