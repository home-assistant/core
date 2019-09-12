"""Test deCONZ remote events."""
import pytest

from unittest.mock import Mock

from homeassistant.components.deconz import deconz_event


@pytest.mark.skip(reason="fails for unkown reason, will refactor in a separate PR")
async def test_create_event(hass):
    """Successfully created a deCONZ event."""
    mock_remote = Mock()
    mock_remote.name = "Name"

    mock_gateway = Mock()
    mock_gateway.hass = hass

    event = deconz_event.DeconzEvent(mock_remote, mock_gateway)

    assert event.event_id == "name"


async def test_update_event(hass):
    """Successfully update a deCONZ event."""
    hass.bus.async_fire = Mock()

    mock_remote = Mock()
    mock_remote.name = "Name"

    mock_gateway = Mock()
    mock_gateway.hass = hass

    event = deconz_event.DeconzEvent(mock_remote, mock_gateway)
    mock_remote.changed_keys = {"state": True}
    event.async_update_callback()

    assert len(hass.bus.async_fire.mock_calls) == 1


@pytest.mark.skip(reason="fails for unkown reason, will refactor in a separate PR")
async def test_remove_event(hass):
    """Successfully update a deCONZ event."""
    mock_remote = Mock()
    mock_remote.name = "Name"

    mock_gateway = Mock()
    mock_gateway.hass = hass

    event = deconz_event.DeconzEvent(mock_remote, mock_gateway)
    event.async_will_remove_from_hass()

    assert event._device is None
