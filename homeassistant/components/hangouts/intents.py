"""Intents for the Hangouts component."""
from homeassistant.helpers import intent
import homeassistant.helpers.config_validation as cv

from .const import CONF_BOT, DOMAIN, INTENT_HELP


class HelpIntent(intent.IntentHandler):
    """Handle Help intents."""

    intent_type = INTENT_HELP
    slot_schema = {
        'conv_id': cv.string
    }

    def __init__(self, hass):
        """Set up the intent."""
        self.hass = hass

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        slots = self.async_validate_slots(intent_obj.slots)
        conv_id = slots['conv_id']['value']

        intents = self.hass.data[DOMAIN][CONF_BOT].get_intents(conv_id)
        response = intent_obj.create_response()
        help_text = "I understand the following sentences:"
        for intent_data in intents.values():
            for sentence in intent_data['sentences']:
                help_text += "\n'{}'".format(sentence)
        response.async_set_speech(help_text)

        return response
