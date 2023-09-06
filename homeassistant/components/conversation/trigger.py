"""Offer sentence based automation rules."""
from __future__ import annotations

from typing import Any

from hassil.recognize import PUNCTUATION, RecognizeResult
import voluptuous as vol

from homeassistant.const import CONF_COMMAND, CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import HOME_ASSISTANT_AGENT, _get_agent_manager
from .const import DOMAIN
from .default_agent import DefaultAgent


def has_no_punctuation(value: list[str]) -> list[str]:
    """Validate result does not contain punctuation."""
    for sentence in value:
        if PUNCTUATION.search(sentence):
            raise vol.Invalid("sentence should not contain punctuation")

    return value


TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DOMAIN,
        vol.Required(CONF_COMMAND): vol.All(
            cv.ensure_list, [cv.string], has_no_punctuation
        ),
    }
)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for events based on configuration."""
    trigger_data = trigger_info["trigger_data"]
    sentences = config.get(CONF_COMMAND, [])

    job = HassJob(action)

    @callback
    async def call_action(sentence: str, result: RecognizeResult) -> str | None:
        """Call action with right context."""

        # Add slot values as extra trigger data
        details = {
            entity_name: {
                "name": entity_name,
                "text": entity.text.strip(),  # remove whitespace
                "value": entity.value.strip()
                if isinstance(entity.value, str)
                else entity.value,
            }
            for entity_name, entity in result.entities.items()
        }

        trigger_input: dict[str, Any] = {  # Satisfy type checker
            **trigger_data,
            "platform": DOMAIN,
            "sentence": sentence,
            "details": details,
            "slots": {  # direct access to values
                entity_name: entity["value"] for entity_name, entity in details.items()
            },
        }

        # Wait for the automation to complete
        if future := hass.async_run_hass_job(
            job,
            {"trigger": trigger_input},
        ):
            await future

        return "Done"

    default_agent = await _get_agent_manager(hass).async_get_agent(HOME_ASSISTANT_AGENT)
    assert isinstance(default_agent, DefaultAgent)

    return default_agent.register_trigger(sentences, call_action)
