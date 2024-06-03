"""Support for Dialogflow webhook."""

import logging

from aiohttp import web
import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_flow, intent, template

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SOURCE = "Home Assistant Dialogflow"

CONFIG_SCHEMA = vol.Schema({DOMAIN: {}}, extra=vol.ALLOW_EXTRA)

V1 = 1
V2 = 2


class DialogFlowError(HomeAssistantError):
    """Raised when a DialogFlow error happens."""


async def handle_webhook(hass, webhook_id, request):
    """Handle incoming webhook with Dialogflow requests."""
    message = await request.json()

    _LOGGER.debug("Received Dialogflow request: %s", message)

    try:
        response = await async_handle_message(hass, message)
        return b"" if response is None else web.json_response(response)

    except DialogFlowError as err:
        _LOGGER.warning(str(err))
        return web.json_response(dialogflow_error_response(message, str(err)))

    except intent.UnknownIntent as err:
        _LOGGER.warning(str(err))
        return web.json_response(
            dialogflow_error_response(
                message, "This intent is not yet configured within Home Assistant."
            )
        )

    except intent.InvalidSlotInfo as err:
        _LOGGER.warning(str(err))
        return web.json_response(
            dialogflow_error_response(
                message, "Invalid slot information received for this intent."
            )
        )

    except intent.IntentError as err:
        _LOGGER.warning(str(err))
        return web.json_response(
            dialogflow_error_response(message, "Error handling intent.")
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure based on config entry."""
    webhook.async_register(
        hass, DOMAIN, "DialogFlow", entry.data[CONF_WEBHOOK_ID], handle_webhook
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    return True


async_remove_entry = config_entry_flow.webhook_async_remove_entry


def dialogflow_error_response(message, error):
    """Return a response saying the error message."""
    api_version = get_api_version(message)
    if api_version is V1:
        parameters = message["result"]["parameters"]
    elif api_version is V2:
        parameters = message["queryResult"]["parameters"]
    dialogflow_response = DialogflowResponse(parameters, api_version)
    dialogflow_response.add_speech(error)
    return dialogflow_response.as_dict()


def get_api_version(message):
    """Get API version of Dialogflow message."""
    if message.get("id") is not None:
        return V1
    if message.get("responseId") is not None:
        return V2


async def async_handle_message(hass, message):
    """Handle a DialogFlow message."""
    _api_version = get_api_version(message)
    if _api_version is V1:
        _LOGGER.warning(
            "Dialogflow V1 API will be removed on October 23, 2019. Please change your"
            " DialogFlow settings to use the V2 api"
        )
        req = message.get("result")
        if req.get("actionIncomplete", True):
            return None

    elif _api_version is V2:
        req = message.get("queryResult")
        if req.get("allRequiredParamsPresent", False) is False:
            return None

    action = req.get("action", "")
    parameters = req.get("parameters").copy()
    parameters["dialogflow_query"] = message
    dialogflow_response = DialogflowResponse(parameters, _api_version)

    if action == "":
        raise DialogFlowError(
            "You have not defined an action in your Dialogflow intent."
        )

    intent_response = await intent.async_handle(
        hass,
        DOMAIN,
        action,
        {key: {"value": value} for key, value in parameters.items()},
    )

    if "plain" in intent_response.speech:
        dialogflow_response.add_speech(intent_response.speech["plain"]["speech"])

    return dialogflow_response.as_dict()


class DialogflowResponse:
    """Help generating the response for Dialogflow."""

    def __init__(self, parameters, api_version):
        """Initialize the Dialogflow response."""
        self.speech = None
        self.parameters = {}
        self.api_version = api_version
        # Parameter names replace '.' and '-' for '_'
        for key, value in parameters.items():
            underscored_key = key.replace(".", "_").replace("-", "_")
            self.parameters[underscored_key] = value

    def add_speech(self, text):
        """Add speech to the response."""
        assert self.speech is None

        if isinstance(text, template.Template):
            text = text.async_render(self.parameters, parse_result=False)

        self.speech = text

    def as_dict(self):
        """Return response in a Dialogflow valid dictionary."""
        if self.api_version is V1:
            return {"speech": self.speech, "displayText": self.speech, "source": SOURCE}

        if self.api_version is V2:
            return {"fulfillmentText": self.speech, "source": SOURCE}
