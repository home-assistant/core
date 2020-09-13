"""The tests for the Canary alarm_control_panel platform."""
from homeassistant.components.canary import DOMAIN
from homeassistant.setup import async_setup_component

from . import mock_device, mock_location, mock_reading

from tests.async_mock import patch
from tests.common import mock_registry


async def test_alarm_control_panel(hass, canary) -> None:
    """Test the creation and values of the alarm_control_panel for Canary."""
    await async_setup_component(hass, "persistent_notification", {})

    registry = mock_registry(hass)
    online_device_at_home = mock_device(20, "Dining Room", True, "Canary Pro")

    instance = canary.return_value
    instance.get_locations.return_value = [
        mock_location(100, "Home", True, devices=[online_device_at_home]),
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
    assert state.state == None
