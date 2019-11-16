"""
Support for Rhasspy voice assistant integration.

For more details about this integration, please refer to the documentation at
https://home-assistant.io/integrations/rhasspy/
"""
import asyncio
import logging
import re
from typing import Dict, Optional
from urllib.parse import urljoin

from num2words import num2words
import voluptuous as vol

from homeassistant.components.conversation import async_set_agent
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import callback
from homeassistant.helpers import intent
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_API_URL,
    CONF_CUSTOM_WORDS,
    CONF_HANDLE_INTENTS,
    CONF_INTENT_COMMANDS,
    CONF_INTENT_FILTERS,
    CONF_INTENT_STATES,
    CONF_LANGUAGE,
    CONF_MAKE_INTENT_COMMANDS,
    CONF_NAME_REPLACE,
    CONF_REGISTER_CONVERSATION,
    CONF_RESPONSE_TEMPLATES,
    CONF_SHOPPING_LIST_ITEMS,
    CONF_SLOTS,
    CONF_TRAIN_TIMEOUT,
    DOMAIN,
    INTENT_DEVICE_STATE,
    INTENT_IS_COVER_CLOSED,
    INTENT_IS_COVER_OPEN,
    INTENT_IS_DEVICE_OFF,
    INTENT_IS_DEVICE_ON,
    INTENT_IS_DEVICE_STATE,
    INTENT_SET_TIMER,
    INTENT_TIMER_READY,
    INTENT_TRIGGER_AUTOMATION,
    INTENT_TRIGGER_AUTOMATION_LATER,
    KEY_COMMAND,
    KEY_COMMAND_TEMPLATE,
    KEY_COMMAND_TEMPLATES,
    KEY_COMMANDS,
    KEY_DATA,
    KEY_DATA_TEMPLATE,
    KEY_DOMAINS,
    KEY_ENTITIES,
    KEY_EXCLUDE,
    KEY_INCLUDE,
    KEY_REGEX,
    SERVICE_TRAIN,
    SUPPORT_LANGUAGES,
)
from .conversation import RhasspyConversationAgent
from .core import EntityCommandInfo
from .default_settings import (
    DEFAULT_API_URL,
    DEFAULT_CUSTOM_WORDS,
    DEFAULT_HANDLE_INTENTS,
    DEFAULT_INTENT_STATES,
    DEFAULT_LANGUAGE,
    DEFAULT_MAKE_INTENT_COMMANDS,
    DEFAULT_NAME_REPLACE,
    DEFAULT_REGISTER_CONVERSATION,
    DEFAULT_RESPONSE_TEMPLATES,
    DEFAULT_SHOPPING_LIST_ITEMS,
    DEFAULT_SLOTS,
    DEFAULT_TRAIN_TIMEOUT,
)
from .intent_handlers import (
    DeviceStateIntent,
    IsDeviceStateIntent,
    SetTimerIntent,
    TimerReadyIntent,
    TriggerAutomationIntent,
    TriggerAutomationLaterIntent,
    make_state_handler,
)
from .training import train_rhasspy

# -----------------------------------------------------------------------------

_LOGGER = logging.getLogger(__name__)

# Config
COMMAND_SCHEMA = vol.Schema(
    {
        vol.Exclusive(KEY_COMMAND, "commands"): str,
        vol.Exclusive(KEY_COMMAND_TEMPLATE, "commands"): cv.template,
        vol.Exclusive(KEY_COMMANDS, "commands"): vol.All(cv.ensure_list, [str]),
        vol.Exclusive(KEY_COMMAND_TEMPLATES, "commands"): vol.All(
            cv.ensure_list, [cv.template]
        ),
        vol.Optional(KEY_DATA): vol.Schema({str: object}),
        vol.Optional(KEY_DATA_TEMPLATE): vol.Schema({str: cv.template}),
        vol.Optional(KEY_INCLUDE): vol.Schema(
            {vol.Optional(KEY_DOMAINS): vol.All(cv.ensure_list, [str])},
            {vol.Optional(KEY_ENTITIES): vol.All(cv.ensure_list, [cv.entity_id])},
        ),
        vol.Optional(KEY_EXCLUDE): vol.Schema(
            {vol.Optional(KEY_ENTITIES): vol.All(cv.ensure_list, [cv.entity_id])}
        ),
        vol.Optional(CONF_HANDLE_INTENTS, DEFAULT_HANDLE_INTENTS): vol.Schema(
            cv.ensure_list, [str]
        ),
        vol.Optional(CONF_RESPONSE_TEMPLATES): vol.Schema({str: cv.template}),
    }
)

INTENT_FILTER_SCHEMA = vol.Schema(
    {
        vol.Optional(KEY_INCLUDE): vol.Schema(
            {vol.Optional(KEY_DOMAINS): vol.All(cv.ensure_list, [str])},
            {vol.Optional(KEY_ENTITIES): vol.All(cv.ensure_list, [cv.entity_id])},
        ),
        vol.Optional(KEY_EXCLUDE): vol.Schema(
            {vol.Optional(KEY_DOMAINS): vol.All(cv.ensure_list, [str])},
            {vol.Optional(KEY_ENTITIES): vol.All(cv.ensure_list, [cv.entity_id])},
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            {
                vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.All(
                    str, vol.In(SUPPORT_LANGUAGES)
                ),
                vol.Optional(CONF_API_URL, default=DEFAULT_API_URL): cv.url,
                vol.Optional(
                    CONF_REGISTER_CONVERSATION, default=DEFAULT_REGISTER_CONVERSATION
                ): bool,
                vol.Optional(CONF_SLOTS): vol.Schema(
                    {str: vol.All(cv.ensure_list, [str])}
                ),
                vol.Optional(CONF_CUSTOM_WORDS, DEFAULT_CUSTOM_WORDS): vol.Schema(
                    {str: str}
                ),
                vol.Optional(CONF_INTENT_COMMANDS): vol.Schema(
                    {str: vol.All(cv.ensure_list, [str, COMMAND_SCHEMA])}
                ),
                vol.Optional(CONF_NAME_REPLACE): {
                    vol.Optional(KEY_REGEX, {}): vol.All(
                        cv.ensure_list, [vol.Schema({str: str})]
                    ),
                    vol.Optional(KEY_ENTITIES, {}): vol.Schema({cv.entity_id: str}),
                },
                vol.Optional(CONF_INTENT_STATES): vol.Schema(
                    {str: vol.All(cv.ensure_list, [str])}
                ),
                vol.Optional(CONF_INTENT_FILTERS): vol.Schema(
                    {str: INTENT_FILTER_SCHEMA}
                ),
                vol.Optional(CONF_TRAIN_TIMEOUT, DEFAULT_TRAIN_TIMEOUT): float,
                vol.Optional(
                    CONF_SHOPPING_LIST_ITEMS, DEFAULT_SHOPPING_LIST_ITEMS
                ): vol.All(cv.ensure_list, [str]),
                vol.Optional(
                    CONF_MAKE_INTENT_COMMANDS, default=DEFAULT_MAKE_INTENT_COMMANDS
                ): vol.Any(
                    bool,
                    vol.Schema(
                        {
                            vol.Exclusive(
                                KEY_INCLUDE, CONF_MAKE_INTENT_COMMANDS
                            ): vol.All(cv.ensure_list, [str]),
                            vol.Exclusive(
                                KEY_EXCLUDE, CONF_MAKE_INTENT_COMMANDS
                            ): vol.All(cv.ensure_list, [str]),
                        }
                    ),
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_SERVICE_TRAIN = vol.Schema({})

# -----------------------------------------------------------------------------


async def async_setup(hass, config):
    """Set up Rhasspy integration."""
    conf = config.get(DOMAIN)
    if conf is None:
        # Don't initialize
        return True

    # Load configuration
    api_url = conf.get(CONF_API_URL, DEFAULT_API_URL)
    if not api_url.endswith("/"):
        api_url = api_url + "/"
        conf[CONF_API_URL] = api_url

    # Create Rhasspy provider.
    # Shared with conversation agent/stt platform.
    provider = RhasspyProvider(hass, conf)
    await provider.async_initialize()

    hass.data[DOMAIN] = provider

    # Register conversation agent
    register_conversation = conf.get(
        CONF_REGISTER_CONVERSATION, DEFAULT_REGISTER_CONVERSATION
    )

    if register_conversation:
        # Register converation agent
        agent = RhasspyConversationAgent(hass, provider.intent_url)
        async_set_agent(hass, agent)
        _LOGGER.debug("Registered Rhasspy conversation agent")

    # Register services
    async def async_train_handle(service):
        """Service handler for training."""
        _LOGGER.debug("Re-training profile")
        await train_rhasspy(provider)

    hass.services.async_register(
        DOMAIN, SERVICE_TRAIN, async_train_handle, schema=SCHEMA_SERVICE_TRAIN
    )

    return True


# -----------------------------------------------------------------------------


class RhasspyProvider:
    """
    Holds configuration for Rhasspy integration.

    Manages voice command generation.
    Handles re-training remote Rhasspy server.
    """

    def __init__(self, hass, config):
        """Set up Rhasspy provider."""
        self.hass = hass
        self.config = config

        # Base URL of Rhasspy web server
        self.api_url: str = config.get(CONF_API_URL, DEFAULT_API_URL)

        # URL to POST sentences.ini
        self.sentences_url: str = urljoin(self.api_url, "sentences")

        # URL to POST custom_words.txt
        self.custom_words_url: str = urljoin(self.api_url, "custom-words")

        # URL to POST slots
        self.slots_url: str = urljoin(self.api_url, "slots")

        # URL to train profile
        self.train_url: str = urljoin(self.api_url, "train")

        # URL for intent recognition
        self.intent_url: str = urljoin(self.api_url, "text-to-intent")

        # e.g., en-US
        self.language: str = config.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)

        # entity_id -> EntityCommandInfo
        self.entities: Dict[str, EntityCommandInfo] = {}

        # Language-specific name replacements
        self.name_replace = dict(
            DEFAULT_NAME_REPLACE.get(
                self.language, DEFAULT_NAME_REPLACE[DEFAULT_LANGUAGE]
            )
        )
        for key, value in self.config.get(CONF_NAME_REPLACE, {}).items():
            # Overwrite with user settings
            self.name_replace[key] = value

        # Regex replacements for cleaning names
        self.name_regexes = self.name_replace.get(KEY_REGEX, {})

        # Language used for num2words (en-US -> en_US)
        self.num2words_lang = self.language.replace("-", "_")
        if self.language == "sv-SV":
            # Use Danish numbers, since Swedish is not supported.
            self.num2words_lang = "dk"

        # Training events
        self.train_handle: Optional[asyncio.Handle] = None
        self.train_timeout = self.config.get(CONF_TRAIN_TIMEOUT, DEFAULT_TRAIN_TIMEOUT)

    # -------------------------------------------------------------------------

    async def async_initialize(self):
        """Initialize Rhasspy provider."""
        # Get intent responses
        response_templates = dict(
            DEFAULT_RESPONSE_TEMPLATES.get(
                self.language, DEFAULT_RESPONSE_TEMPLATES[DEFAULT_LANGUAGE]
            )
        )
        if CONF_RESPONSE_TEMPLATES in self.config:
            for intent_name, template in self.config[CONF_RESPONSE_TEMPLATES].items():
                # Overwrite defaults
                response_templates[intent_name] = template

        # Get state names for state-based intents
        intent_states = dict(
            DEFAULT_INTENT_STATES.get(
                self.language, DEFAULT_INTENT_STATES[DEFAULT_LANGUAGE]
            )
        )
        if CONF_INTENT_STATES in self.config:
            for intent_name, states in self.config[CONF_INTENT_STATES].items():
                # Overwrite defaults
                intent_states[intent_name] = states

        # Register intent handlers.
        # Pass in response (speech) templates to some handlers.
        handle_intents = set(
            self.config.get(CONF_HANDLE_INTENTS, DEFAULT_HANDLE_INTENTS)
        )

        if INTENT_IS_DEVICE_STATE in handle_intents:
            intent.async_register(
                self.hass,
                IsDeviceStateIntent(response_templates[INTENT_IS_DEVICE_STATE]),
            )

        if INTENT_DEVICE_STATE in handle_intents:
            intent.async_register(
                self.hass, DeviceStateIntent(response_templates[INTENT_DEVICE_STATE])
            )

        # Generate handlers for specific states (on, open, etc.)
        for state_intent in [
            INTENT_IS_DEVICE_ON,
            INTENT_IS_DEVICE_OFF,
            INTENT_IS_COVER_OPEN,
            INTENT_IS_COVER_CLOSED,
        ]:
            if state_intent in handle_intents:
                intent.async_register(
                    self.hass,
                    make_state_handler(
                        state_intent,
                        intent_states[state_intent],
                        response_templates[state_intent],
                    ),
                )

        if INTENT_SET_TIMER in handle_intents:
            intent.async_register(self.hass, SetTimerIntent())

        if INTENT_TIMER_READY in handle_intents:
            intent.async_register(
                self.hass, TimerReadyIntent(response_templates[INTENT_TIMER_READY])
            )

        if INTENT_TRIGGER_AUTOMATION in handle_intents:
            intent.async_register(
                self.hass,
                TriggerAutomationIntent(response_templates[INTENT_TRIGGER_AUTOMATION]),
            )

        if INTENT_TRIGGER_AUTOMATION_LATER in handle_intents:
            intent.async_register(self.hass, TriggerAutomationLaterIntent())

        # Generate default slots.
        # Numbers zero to one hundred.
        number_0_100 = []
        for number in range(0, 101):
            try:
                number_str = num2words(number, lang=self.num2words_lang)
            except NotImplementedError:
                # Use default language (U.S. English)
                number_str = num2words(number)

            # Clean up dashes, etc.
            number_str = self.clean_name(number_str)

            # Add substitutions, so digits will show up downstream instead of
            # words.
            words = re.split(r"\s+", number_str)
            for i, word in enumerate(words):
                if i == 0:
                    words[i] = f"{word}:{number}"
                else:
                    words[i] = word + ":"

            number_0_100.append(" ".join(words))

        DEFAULT_SLOTS["number_0_100"] = number_0_100

        # Register for component loaded event
        self.hass.bus.async_listen(EVENT_COMPONENT_LOADED, self.component_loaded)

    @callback
    def component_loaded(self, event):
        """Handle a new component loaded."""
        old_entity_count = len(self.entities)

        # User-defined entity names for speech to text
        entity_name_map = self.name_replace.get(KEY_ENTITIES, {})

        for state in self.hass.states.async_all():
            # Skip entities that have already been loaded
            if state.entity_id in self.entities:
                continue

            if state.entity_id in entity_name_map:
                # User-defined name
                speech_name = entity_name_map[state.entity_id]
            else:
                # Try to clean name
                speech_name = self.clean_name(state.name)

            # Clean name but don't replace numbers.
            # This should be matched by intent.async_match_state.
            friendly_name = state.name.replace("_", " ")

            info = EntityCommandInfo(
                entity_id=state.entity_id,
                state=state,
                speech_name=speech_name,
                friendly_name=friendly_name,
            )

            self.entities[state.entity_id] = info

        # Detemine if new entities have been added
        if len(self.entities) > old_entity_count:
            _LOGGER.debug("Need to retrain profile")
            self.schedule_retrain()

    def clean_name(self, name: str, replace_numbers=True) -> str:
        """
        Prepare an entity name for speech recognition.

        Replace numbers with words.
        Perform regex substitution using name_replace parameter.
        """
        # Do regex substitution
        for replacements in self.name_regexes:
            for pattern, replacement in replacements.items():
                name = re.sub(pattern, replacement, name)

        if replace_numbers:
            # Do number replacement
            words = re.split(r"\s+", name)
            changed = False

            # Convert numbers to words.
            # e.g., 75 -> seventy five
            for i, word in enumerate(words):
                try:
                    number = float(word)
                    try:
                        words[i] = num2words(number, lang=self.num2words_lang)
                    except NotImplementedError:
                        # Use default language (U.S. English)
                        words[i] = num2words(number)

                    changed = True

                    # seventy-five -> seventy five
                    words[i] = words[i].replace("-", " ")
                except ValueError:
                    pass

            if changed:
                # Re-create name
                name = " ".join(words)

        return name

    # -------------------------------------------------------------------------

    def schedule_retrain(self):
        """Reset re-train timer. Train Rhasspy when it elapses."""
        if self.train_handle is not None:
            # Cancel previously scheduled training
            self.train_handle.cancel()
            self.train_handle = None

        # Schedule new training
        self.train_handle = asyncio.create_task(self._wait_retrain())

    async def _wait_retrain(self):
        """Count down a timer and triggers a re-train when it reaches zero."""
        # Wait for timeout
        await asyncio.sleep(self.train_timeout)

        try:
            # Do training
            await train_rhasspy(self)
            _LOGGER.debug("Ready")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("train")
