"""Offer sentence based automation rules."""

from __future__ import annotations

from typing import Any

from hassil.recognize import PUNCTUATION, RecognizeResult
import voluptuous as vol

from homeassistant.const import CONF_COMMAND, CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.script import ScriptRunResult
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import UNDEFINED, ConfigType

from .const import DOMAIN
from .default_agent import DefaultAgent, async_get_default_agent


def has_no_punctuation(value: list[str]) -> list[str]:
    """Validate result does not contain punctuation."""
    for sentence in value:
        if PUNCTUATION.search(sentence):
            raise vol.Invalid("sentence should not contain punctuation")

    return value


def has_one_non_empty_item(value: list[str]) -> list[str]:
    """Validate result has at least one item."""
    if len(value) < 1:
        raise vol.Invalid("at least one sentence is required")

    for sentence in value:
        if not sentence:
            raise vol.Invalid(f"sentence too short: '{sentence}'")

    return value


TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DOMAIN,
        vol.Required(CONF_COMMAND): vol.All(
            cv.ensure_list, [cv.string], has_one_non_empty_item, has_no_punctuation
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

    async def call_action(
        sentence: str, result: RecognizeResult, device_id: str | None
    ) -> str | None:
        """Call action with right context."""

        # Add slot values as extra trigger data
        details = {
            entity_name: {
                "name": entity_name,
                "text": entity.text.strip(),  # remove whitespace
                "value": (
                    entity.value.strip()
                    if isinstance(entity.value, str)
                    else entity.value
                ),
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
            "device_id": device_id,
        }

        # Wait for the automation to complete
        if future := hass.async_run_hass_job(
            job,
            {"trigger": trigger_input},
        ):
            automation_result = await future
            if isinstance(
                automation_result, ScriptRunResult
            ) and automation_result.conversation_response not in (None, UNDEFINED):
                # mypy does not understand the type narrowing, unclear why
                return automation_result.conversation_response  # type: ignore[return-value]

        # It's important to return None here instead of a string.
        #
        # When editing in the UI, a copy of this trigger is registered.
        # If we return a string from here, there is a race condition between the
        # two trigger copies for who will provide a response.
        return None

    default_agent = async_get_default_agent(hass)
    assert isinstance(default_agent, DefaultAgent)

    return default_agent.register_trigger(sentences, call_action)
