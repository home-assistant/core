"""The tests for the Canary alarm_control_panel platform."""
from canary.api import LOCATION_MODE_AWAY, LOCATION_MODE_HOME, LOCATION_MODE_NIGHT

from homeassistant.components.canary import DOMAIN
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
)
from homeassistant.setup import async_setup_component

from . import mock_device, mock_location, mock_mode

from tests.async_mock import patch
from tests.common import mock_registry


async def test_alarm_control_panel(hass, canary) -> None:
    """Test the creation and values of the alarm_control_panel for Canary."""
    await async_setup_component(hass, "persistent_notification", {})

    registry = mock_registry(hass)
    online_device_at_home = mock_device(20, "Dining Room", True, "Canary Pro")

    mock_location = mock_location(
        location_id=100,
        name="Home",
        is_online=True,
        is_private=True,
        devices=[online_device_at_home],
    )

    instance = canary.return_value
    instance.get_locations.return_value = [
       mock_location
    ]

    config = {DOMAIN: {"username": "test-username", "password": "test-password"}}
    with patch("homeassistant.components.canary.CANARY_COMPONENTS", ["alarm_control_panel"]):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    entity_id = "alarm_control_panel.home"
    entity_entry = registry.async_get(entity_id)
    assert not entity_entry

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ALARM_DISARMED
    assert state.attributes["private"] == "True"

    mock_location.is_private = False

    # test armed home
    mock_location.mode.return_value = mock_mode(4, LOCATION_MODE_HOME)

    await hass.helpers.entity_component.async_update_entity(entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ALARM_ARMED_HOME

    # test armed away
    mock_location.mode.return_value = mock_mode(5, LOCATION_MODE_AWAY)

    await hass.helpers.entity_component.async_update_entity(entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ALARM_ARMED_AWAY

    # test armed night
    mock_location.mode.return_value = mock_mode(6, LOCATION_MODE_NIGHT)

    await hass.helpers.entity_component.async_update_entity(entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ALARM_ARMED_NIGHT
