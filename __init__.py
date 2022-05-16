"""Handle intents with scripts."""
from __future__ import annotations

import copy
import typing

import voluptuous as vol

import homeassistant.const as const
import homeassistant.core as core
import homeassistant.helpers as helpers
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.typing as ha_typing

DOMAIN: typing.Final = "intent_script"

CONF_INTENTS: typing.Final = "intents"
CONF_SPEECH: typing.Final = "speech"
CONF_REPROMPT: typing.Final = "reprompt"

CONF_ACTION: typing.Final = "action"
CONF_CARD: typing.Final = "card"
CONF_TITLE: typing.Final = "title"
CONF_CONTENT: typing.Final = "content"
CONF_TEXT: typing.Final = "text"
CONF_ASYNC_ACTION: typing.Final = "async_action"
CONF_EXTRA_DATA: typing.Final = "extra_data"

DEFAULT_CONF_ASYNC_ACTION: typing.Final = False

CONFIG_SCHEMA: typing.Final = vol.Schema(
    {
        DOMAIN: {
            cv.string: {
                vol.Optional(CONF_ACTION): cv.SCRIPT_SCHEMA,
                vol.Optional(
                    CONF_ASYNC_ACTION, default=DEFAULT_CONF_ASYNC_ACTION
                ): cv.boolean,
                vol.Optional(CONF_CARD): {
                    vol.Optional(const.CONF_TYPE, default="simple"): cv.string,
                    vol.Required(CONF_TITLE): cv.template,
                    vol.Required(CONF_CONTENT): cv.template,
                },
                vol.Optional(CONF_SPEECH): {
                    vol.Optional(const.CONF_TYPE, default="plain"): cv.string,
                    vol.Required(CONF_TEXT): cv.template,
                },
                vol.Optional(CONF_REPROMPT): {
                    vol.Optional(const.CONF_TYPE, default="plain"): cv.string,
                    vol.Required(CONF_TEXT): cv.template,
                },
            }
        }
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: core.HomeAssistant, config: ha_typing.ConfigType) -> bool:
    """Activate Alexa component."""
    intents = copy.deepcopy(config[DOMAIN])
    helpers.template.attach(hass, intents)

    for intent_type, conf in intents.items():
        if CONF_ACTION in conf:
            conf[CONF_ACTION] = helpers.script.Script(
                hass, conf[CONF_ACTION], f"Intent Script {intent_type}", DOMAIN
            )
        helpers.intent.async_register(hass, ScriptIntentHandler(intent_type, conf))

    return True


class ScriptIntentHandler(helpers.intent.IntentHandler):
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
            extra_data = speech.get(CONF_EXTRA_DATA, None)
            response.async_set_speech(
                speech[CONF_TEXT].async_render(slots, parse_result=False),
                speech[const.CONF_TYPE],
                extra_data,
            )

        if reprompt is not None and reprompt[CONF_TEXT].template:
            extra_data = reprompt.get(CONF_EXTRA_DATA, None)
            response.async_set_reprompt(
                reprompt[CONF_TEXT].async_render(slots, parse_result=False),
                reprompt[const.CONF_TYPE],
                extra_data,
            )

        if card is not None:
            extra_data = card.get(CONF_EXTRA_DATA, None)
            response.async_set_card(
                card[CONF_TITLE].async_render(slots, parse_result=False),
                card[CONF_CONTENT].async_render(slots, parse_result=False),
                card[const.CONF_TYPE],
                extra_data,
            )

        return response
