"""Register script intents."""
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .const import DOMAIN

INTENT_MORNING = "HassMorning"
INTENT_BEDTIME = "HassBedtime"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the script intents."""
    intent.async_register(
        hass,
        ScriptIntentHandler(INTENT_MORNING, "morning", "Good morning"),
    )
    intent.async_register(
        hass,
        ScriptIntentHandler(INTENT_BEDTIME, "bedtime", "Goodnight"),
    )


class ScriptIntentHandler(intent.IntentHandler):
    """Run a script if exists."""

    def __init__(self, intent_type: str, script_id: str, speech: str) -> None:
        """Create Service Intent Handler."""
        self.intent_type = intent_type
        self.script_id = script_id
        self.speech = speech

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the hass intent."""
        hass = intent_obj.hass

        response = intent_obj.create_response()
        if hass.states.get(DOMAIN + "." + self.script_id) is None:
            response.async_set_speech("Script not found")
        else:
            await hass.services.async_call(DOMAIN, self.script_id)
            response.async_set_speech(self.speech)

        return response
