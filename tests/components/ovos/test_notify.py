"""Test the OVOS config flow."""
from unittest.mock import MagicMock

from ovos_bus_client import MessageBusClient

from homeassistant.components.ovos import DOMAIN
from homeassistant.components.ovos.notify import get_service
from homeassistant.core import HomeAssistant


class MessageBusClientMock(MessageBusClient):
    """Mock MessageBusClient."""

    def __init__(self):
        """Skip configuration."""
        pass


async def test_send_message(hass: HomeAssistant) -> None:
    """Test sending a message in the notification service."""
    message_bus_client = MessageBusClientMock()
    message_bus_client.emit = MagicMock()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("entries", {})
    hass.data[DOMAIN]["entries"]["id"] = {"client": message_bus_client}

    service = get_service(hass, {})
    service.send_message("testing notifications")

    message = message_bus_client.emit.call_args.args[0]
    assert (message.msg_type) == "speak"
    assert (message.data) == {"utterance": "testing notifications", "lang": "en-us"}
