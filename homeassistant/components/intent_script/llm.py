"""LLM tools for the intent_script integration."""

import slugify as unicode_slug

from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent
from homeassistant.helpers.llm import IntentTool, LLMContext, Tool

from . import ScriptIntentHandler


@callback
def async_get_tools(hass: HomeAssistant, llm_context: LLMContext) -> LLMTools:
    """Return an LLM tool for each configured intent script."""
    handlers = [
        handler
        for handler in intent.async_get(hass)
        if isinstance(handler, ScriptIntentHandler)
    ]

    exposed_domains = {
        state.domain
        for state in hass.states.async_all()
        if async_should_expose(hass, llm_context.assistant, state.entity_id)
    }
    handlers = [
        handler
        for handler in handlers
        if handler.platforms is None or handler.platforms & exposed_domains
    ]

    # Intent script names come from user configuration, so slugify them into
    # valid tool names.
    tools: list[Tool] = [
        IntentTool(
            unicode_slug.slugify(handler.intent_type, separator="_", lowercase=False),
            handler,
        )
        for handler in handlers
    ]
    return LLMTools(tools=tools)
