"""The Intent integration."""
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.components import http
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.helpers import config_validation as cv, intent

from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Intent component."""
    hass.http.register_view(ConversationHandleView())
    return True


class ConversationHandleView(http.HomeAssistantView):
    """View to handle intents from JSON."""

    url = "/api/intent/handle"
    name = "api:intent:handle"

    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required("name"): cv.string,
                vol.Optional("data"): vol.Schema({cv.string: object}),
            }
        )
    )
    async def post(self, request, data):
        """Handle intent with name/data."""
        hass = request.app["hass"]

        try:
            intent_name = data["name"]
            slots = {
                key: {"value": value} for key, value in data.get("data", {}).items()
            }
            intent_result = await intent.async_handle(
                hass, DOMAIN, intent_name, slots, "", self.context(request)
            )
        except intent.IntentHandleError as err:
            intent_result = intent.IntentResponse()
            intent_result.async_set_speech(str(err))

        if intent_result is None:
            intent_result = intent.IntentResponse()
            intent_result.async_set_speech("Sorry, I couldn't handle that")

        return self.json(intent_result)
