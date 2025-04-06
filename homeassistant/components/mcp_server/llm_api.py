"""LLM API for MCP Server.

This is a modified version of the AssistAPI that does not include the home state
in the prompt. This API is not registered with the LLM API registry since it is
only used by the MCP Server. The MCP server will substitute this API when the
user selects the Assist API.
"""

from homeassistant.core import callback
from homeassistant.helpers import llm
from homeassistant.util import yaml as yaml_util

EXPOSED_ENTITY_FIELDS = {"name", "domain", "description", "areas", "names"}


class StatelessAssistAPI(llm.AssistAPI):
    """LLM API for MCP Server that provides the Assist API without state information in the prompt.

    Syncing the state information is possible, but may put unnecessary load on
    the system so we are instead providing the prompt without entity state. Since
    actions don't care about the current state, there is little quality loss.
    """

    @callback
    def _async_get_exposed_entities_prompt(
        self, llm_context: llm.LLMContext, exposed_entities: dict | None
    ) -> list[str]:
        """Return the prompt for the exposed entities."""
        prompt = []

        if exposed_entities and exposed_entities["entities"]:
            prompt.append(
                "An overview of the areas and the devices in this smart home:"
            )
            entities = [
                {k: v for k, v in entity_info.items() if k in EXPOSED_ENTITY_FIELDS}
                for entity_info in exposed_entities["entities"].values()
            ]
            prompt.append(yaml_util.dump(list(entities)))

        return prompt
