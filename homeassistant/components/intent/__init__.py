"""The Intent integration."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.setup import ATTR_COMPONENT
from homeassistant.components import http
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.loader import async_get_integration, IntegrationNotFound

from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Intent component."""
    hass.http.register_view(IntentHandleView())

    tasks = [_async_process_intent(hass, comp) for comp in hass.config.components]

    async def async_component_loaded(event):
        """Handle a new component loaded."""
        await _async_process_intent(hass, event.data[ATTR_COMPONENT])

    hass.bus.async_listen(EVENT_COMPONENT_LOADED, async_component_loaded)

    if tasks:
        await asyncio.gather(*tasks)

    return True


async def _async_process_intent(hass: HomeAssistant, component_name: str):
    """Process the intents of a component."""
    try:
        integration = await async_get_integration(hass, component_name)
        platform = integration.get_platform(DOMAIN)
    except (IntegrationNotFound, ImportError):
        return

    try:
        await platform.async_setup_intents(hass)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Error setting up intents for %s", component_name)


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
