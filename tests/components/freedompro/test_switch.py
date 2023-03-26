"""Tests for the Freedompro switch."""
from datetime import timedelta
from unittest.mock import ANY, patch

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util.dt import utcnow

from .conftest import get_states_response_for_uid

from tests.common import async_fire_time_changed

uid = "3WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*1JKU1MVWHQL-Z9SCUS85VFXMRGNDCDNDDUVVDKBU31W"


async def test_switch_get_state(hass: HomeAssistant, init_integration) -> None:
    """Test states of the switch."""
    init_integration
    registry = er.async_get(hass)

    entity_id = "switch.irrigation_switch"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get("friendly_name") == "Irrigation switch"

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == uid

    states_response = get_states_response_for_uid(uid)
    states_response[0]["state"]["on"] = True
    with patch(
        "homeassistant.components.freedompro.get_states",
        return_value=states_response,
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state
        assert state.attributes.get("friendly_name") == "Irrigation switch"

        entry = registry.async_get(entity_id)
        assert entry
        assert entry.unique_id == uid

        assert state.state == STATE_ON


async def test_switch_set_off(hass: HomeAssistant, init_integration) -> None:
    """Test set off of the switch."""
    init_integration
    registry = er.async_get(hass)

    entity_id = "switch.irrigation_switch"

    states_response = get_states_response_for_uid(uid)
    states_response[0]["state"]["on"] = True
    with patch(
        "homeassistant.components.freedompro.get_states",
        return_value=states_response,
    ):
        await async_update_entity(hass, entity_id)
        async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get("friendly_name") == "Irrigation switch"

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == uid

    with patch(
        "homeassistant.components.freedompro.switch.put_state"
    ) as mock_put_state:
        assert await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
    mock_put_state.assert_called_once_with(ANY, ANY, ANY, '{"on": false}')

    states_response = get_states_response_for_uid(uid)
    states_response[0]["state"]["on"] = False
    with patch(
        "homeassistant.components.freedompro.get_states",
        return_value=states_response,
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_switch_set_on(hass: HomeAssistant, init_integration) -> None:
    """Test set on of the switch."""
    init_integration
    registry = er.async_get(hass)

    entity_id = "switch.irrigation_switch"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get("friendly_name") == "Irrigation switch"

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == uid

    with patch(
        "homeassistant.components.freedompro.switch.put_state"
    ) as mock_put_state:
        assert await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
    mock_put_state.assert_called_once_with(ANY, ANY, ANY, '{"on": true}')

    states_response = get_states_response_for_uid(uid)
    states_response[0]["state"]["on"] = True
    with patch(
        "homeassistant.components.freedompro.get_states",
        return_value=states_response,
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(hours=2))
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
