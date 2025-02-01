"""LLM API for MCP Server."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent, llm
from homeassistant.util import yaml as yaml_util

EXPOSED_ENTITY_FIELDS = {"name", "domain", "description", "areas", "names"}


def async_register_api(hass: HomeAssistant) -> None:
    """Register the LLM API."""
    llm.async_register_api(hass, StatelessAssistAPI(hass))


class StatelessAssistAPI(llm.AssistAPI):
    """LLM API for MCP Server that provides the Assist API without state information in the prompt."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the StatelessAssistAPI."""
        super().__init__(hass)
        self.id = "stateless_assist"
        self.name = "Stateless Assist"

    # Expose INTENT_GET_STATE
    IGNORE_INTENTS = {
        intent_name
        for intent_name in llm.AssistAPI.IGNORE_INTENTS
        if intent_name not in {intent.INTENT_GET_STATE}
    }

    @callback
    def _async_get_exposed_entities_prompt(
        self, llm_context: llm.LLMContext, exposed_entities: dict | None
    ) -> list[str]:
        """Return the prompt for the exposed entities."""
        prompt = []

        if exposed_entities:
            prompt.append(
                "An overview of the areas and the devices in this smart home:"
            )
            entities = [
                {k: v for k, v in entity_info.items() if k in EXPOSED_ENTITY_FIELDS}
                for entity_info in exposed_entities.values()
            ]
            prompt.append(yaml_util.dump(list(entities)))

        return prompt
