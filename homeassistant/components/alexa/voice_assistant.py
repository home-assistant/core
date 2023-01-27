from homeassistant.core import HomeAssistant
from homeassistant.components.light import DOMAIN


def process_voice_input(hass, voice_input):
    """Process voice input and return output."""
    if voice_input == "turn on the lights":
        hass.services.call("light", "turn_on", {"entity_id": "light.kitchen"})
        return "Lights turned on"
    else:
        return "Command not recognized"
