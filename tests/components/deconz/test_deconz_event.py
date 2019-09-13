"""Test deCONZ remote events."""
from unittest.mock import Mock

from homeassistant.components.deconz.deconz_event import CONF_DECONZ_EVENT, DeconzEvent
from homeassistant.core import callback


async def test_create_event(hass):
    """Successfully created a deCONZ event."""
    mock_remote = Mock()
    mock_remote.name = "Name"

    mock_gateway = Mock()
    mock_gateway.hass = hass

    event = DeconzEvent(mock_remote, mock_gateway)

    assert event.event_id == "name"


async def test_update_event(hass):
    """Successfully update a deCONZ event."""
    mock_remote = Mock()
    mock_remote.name = "Name"

    mock_gateway = Mock()
    mock_gateway.hass = hass

    event = DeconzEvent(mock_remote, mock_gateway)
    mock_remote.changed_keys = {"state": True}

    calls = []

    @callback
    def listener(event):
        """Mock listener."""
        calls.append(event)

    unsub = hass.bus.async_listen(CONF_DECONZ_EVENT, listener)

    event.async_update_callback()
    await hass.async_block_till_done()

    assert len(calls) == 1

    unsub()


async def test_remove_event(hass):
    """Successfully update a deCONZ event."""
    mock_remote = Mock()
    mock_remote.name = "Name"

    mock_gateway = Mock()
    mock_gateway.hass = hass

    event = DeconzEvent(mock_remote, mock_gateway)
    event.async_will_remove_from_hass()

    assert event._device is None
