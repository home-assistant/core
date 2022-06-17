"""The Intent integration."""
import voluptuous as vol

from homeassistant.components import http
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.const import SERVICE_TOGGLE, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import DOMAIN as HA_DOMAIN, HomeAssistant
from homeassistant.helpers import config_validation as cv, integration_platform, intent
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Intent component."""
    hass.http.register_view(IntentHandleView())

    await integration_platform.async_process_integration_platforms(
        hass, DOMAIN, _async_process_intent
    )

    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            intent.INTENT_TURN_ON, HA_DOMAIN, SERVICE_TURN_ON, "Turned {} on"
        ),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            intent.INTENT_TURN_OFF, HA_DOMAIN, SERVICE_TURN_OFF, "Turned {} off"
        ),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            intent.INTENT_TOGGLE, HA_DOMAIN, SERVICE_TOGGLE, "Toggled {}"
        ),
    )

    return True


async def _async_process_intent(hass: HomeAssistant, domain: str, platform):
    """Process the intents of an integration."""
    await platform.async_setup_intents(hass)


class IntentHandleView(http.HomeAssistantView):
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
