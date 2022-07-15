"""Handle intents with scripts."""
import copy

import voluptuous as vol

from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, intent, script, template
from homeassistant.helpers.typing import ConfigType

DOMAIN = "intent_script"

CONF_INTENTS = "intents"
CONF_SPEECH = "speech"
CONF_REPROMPT = "reprompt"

CONF_ACTION = "action"
CONF_CARD = "card"
CONF_TITLE = "title"
CONF_CONTENT = "content"
CONF_TEXT = "text"
CONF_ASYNC_ACTION = "async_action"

DEFAULT_CONF_ASYNC_ACTION = False

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            cv.string: {
                vol.Optional(CONF_ACTION): cv.SCRIPT_SCHEMA,
                vol.Optional(
                    CONF_ASYNC_ACTION, default=DEFAULT_CONF_ASYNC_ACTION
                ): cv.boolean,
                vol.Optional(CONF_CARD): {
                    vol.Optional(CONF_TYPE, default="simple"): cv.string,
                    vol.Required(CONF_TITLE): cv.template,
                    vol.Required(CONF_CONTENT): cv.template,
                },
                vol.Optional(CONF_SPEECH): {
                    vol.Optional(CONF_TYPE, default="plain"): cv.string,
                    vol.Required(CONF_TEXT): cv.template,
                },
                vol.Optional(CONF_REPROMPT): {
                    vol.Optional(CONF_TYPE, default="plain"): cv.string,
                    vol.Required(CONF_TEXT): cv.template,
                },
            }
        }
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Activate Alexa component."""
    intents = copy.deepcopy(config[DOMAIN])
    template.attach(hass, intents)

    for intent_type, conf in intents.items():
        if CONF_ACTION in conf:
            conf[CONF_ACTION] = script.Script(
                hass, conf[CONF_ACTION], f"Intent Script {intent_type}", DOMAIN
            )
        intent.async_register(hass, ScriptIntentHandler(intent_type, conf))

    return True


class ScriptIntentHandler(intent.IntentHandler):
    """Respond to an intent with a script."""

    def __init__(self, intent_type, config):
        """Initialize the script intent handler."""
        self.intent_type = intent_type
        self.config = config

    async def async_handle(self, intent_obj):
        """Handle the intent."""
        speech = self.config.get(CONF_SPEECH)
        reprompt = self.config.get(CONF_REPROMPT)
        card = self.config.get(CONF_CARD)
        action = self.config.get(CONF_ACTION)
        is_async_action = self.config.get(CONF_ASYNC_ACTION)
        slots = {key: value["value"] for key, value in intent_obj.slots.items()}

        if action is not None:
            if is_async_action:
                intent_obj.hass.async_create_task(
                    action.async_run(slots, intent_obj.context)
                )
            else:
                await action.async_run(slots, intent_obj.context)

        response = intent_obj.create_response()

        if speech is not None:
            response.async_set_speech(
                speech[CONF_TEXT].async_render(slots, parse_result=False),
                speech[CONF_TYPE],
            )

        if reprompt is not None:
            text_reprompt = reprompt[CONF_TEXT].async_render(slots, parse_result=False)
            if text_reprompt:
                response.async_set_reprompt(
                    text_reprompt,
                    reprompt[CONF_TYPE],
                )

        if card is not None:
            response.async_set_card(
                card[CONF_TITLE].async_render(slots, parse_result=False),
                card[CONF_CONTENT].async_render(slots, parse_result=False),
                card[CONF_TYPE],
            )

        return response
