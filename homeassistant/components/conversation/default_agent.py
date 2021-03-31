"""Standard conversastion implementation for Home Assistant."""
from __future__ import annotations

import re

from homeassistant import core, setup
from homeassistant.components.cover.intent import INTENT_CLOSE_COVER, INTENT_OPEN_COVER
from homeassistant.components.shopping_list.intent import (
    INTENT_ADD_ITEM,
    INTENT_LAST_ITEMS,
)
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import callback
from homeassistant.helpers import intent
from homeassistant.setup import ATTR_COMPONENT

from .agent import AbstractConversationAgent
from .const import DOMAIN
from .util import create_matcher

REGEX_TURN_COMMAND = re.compile(r"turn (?P<name>(?: |\w)+) (?P<command>\w+)")
REGEX_TYPE = type(re.compile(""))

UTTERANCES = {
    "cover": {
        INTENT_OPEN_COVER: ["Open [the] [a] [an] {name}[s]"],
        INTENT_CLOSE_COVER: ["Close [the] [a] [an] {name}[s]"],
    },
    "shopping_list": {
        INTENT_ADD_ITEM: ["Dodaj [pozycję] {item} do [mojej] [listy] zakupów"],
        INTENT_LAST_ITEMS: ["Co jest na liście zakupów", "Lista zakupów"],
    },
}


@core.callback
def async_register(hass, intent_type, utterances):
    """Register utterances and any custom intents for the default agent.

    Registrations don't require conversations to be loaded. They will become
    active once the conversation component is loaded.
    """
    intents = hass.data.setdefault(DOMAIN, {})
    conf = intents.setdefault(intent_type, [])

    for utterance in utterances:
        if isinstance(utterance, REGEX_TYPE):
            conf.append(utterance)
        else:
            conf.append(create_matcher(utterance))


class DefaultAgent(AbstractConversationAgent):
    """Default agent for conversation agent."""

    def __init__(self, hass: core.HomeAssistant):
        """Initialize the default agent."""
        self.hass = hass

    async def async_initialize(self, config):
        """Initialize the default agent."""
        if "intent" not in self.hass.config.components:
            await setup.async_setup_component(self.hass, "intent", {})

        config = config.get(DOMAIN, {})
        intents = self.hass.data.setdefault(DOMAIN, {})

        for intent_type, utterances in config.get("intents", {}).items():
            conf = intents.get(intent_type)

            if conf is None:
                conf = intents[intent_type] = []

            conf.extend(create_matcher(utterance) for utterance in utterances)

        # We strip trailing 's' from name because our state matcher will fail
        # if a letter is not there. By removing 's' we can match singular and
        # plural names.

        async_register(
            self.hass,
            intent.INTENT_TURN_ON,
            ["Turn [the] [a] {name}[s] on", "Turn on [the] [a] [an] {name}[s]"],
        )
        async_register(
            self.hass,
            intent.INTENT_TURN_OFF,
            ["Turn [the] [a] [an] {name}[s] off", "Turn off [the] [a] [an] {name}[s]"],
        )
        async_register(
            self.hass,
            intent.INTENT_TOGGLE,
            ["Toggle [the] [a] [an] {name}[s]", "[the] [a] [an] {name}[s] toggle"],
        )

        @callback
        def component_loaded(event):
            """Handle a new component loaded."""
            self.register_utterances(event.data[ATTR_COMPONENT])

        self.hass.bus.async_listen(EVENT_COMPONENT_LOADED, component_loaded)

        # Check already loaded components.
        for component in self.hass.config.components:
            self.register_utterances(component)

    @callback
    def register_utterances(self, component):
        """Register utterances for a component."""
        if component not in UTTERANCES:
            return
        for intent_type, sentences in UTTERANCES[component].items():
            async_register(self.hass, intent_type, sentences)

    async def async_process(
        self, text: str, context: core.Context, conversation_id: str | None = None
    ) -> intent.IntentResponse:
        """Process a sentence."""
        intents = self.hass.data[DOMAIN]

        for intent_type, matchers in intents.items():
            for matcher in matchers:
                match = matcher.match(text)

                if not match:
                    continue

                return await intent.async_handle(
                    self.hass,
                    DOMAIN,
                    intent_type,
                    {key: {"value": value} for key, value in match.groupdict().items()},
                    text,
                    context,
                )
