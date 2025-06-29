"""Base class for assist satellite entities."""

from dataclasses import asdict
import logging
from pathlib import Path
from typing import Any

from hassil.util import (
    PUNCTUATION_END,
    PUNCTUATION_END_WORD,
    PUNCTUATION_START,
    PUNCTUATION_START_WORD,
)
import voluptuous as vol

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .connection_test import ConnectionTestView
from .const import (
    CONNECTION_TEST_DATA,
    DATA_COMPONENT,
    DOMAIN,
    PREANNOUNCE_FILENAME,
    PREANNOUNCE_URL,
    AssistSatelliteEntityFeature,
)
from .entity import (
    AssistSatelliteAnnouncement,
    AssistSatelliteAnswer,
    AssistSatelliteConfiguration,
    AssistSatelliteEntity,
    AssistSatelliteEntityDescription,
    AssistSatelliteWakeWord,
)
from .errors import SatelliteBusyError
from .websocket_api import async_register_websocket_api

__all__ = [
    "DOMAIN",
    "AssistSatelliteAnnouncement",
    "AssistSatelliteAnswer",
    "AssistSatelliteConfiguration",
    "AssistSatelliteEntity",
    "AssistSatelliteEntityDescription",
    "AssistSatelliteEntityFeature",
    "AssistSatelliteWakeWord",
    "SatelliteBusyError",
]

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    component = hass.data[DATA_COMPONENT] = EntityComponent[AssistSatelliteEntity](
        _LOGGER, DOMAIN, hass
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        "announce",
        vol.All(
            cv.make_entity_service_schema(
                {
                    vol.Optional("message"): str,
                    vol.Optional("media_id"): _media_id_validator,
                    vol.Optional("preannounce"): bool,
                    vol.Optional("preannounce_media_id"): _media_id_validator,
                }
            ),
            cv.has_at_least_one_key("message", "media_id"),
        ),
        "async_internal_announce",
        [AssistSatelliteEntityFeature.ANNOUNCE],
    )

    component.async_register_entity_service(
        "start_conversation",
        vol.All(
            cv.make_entity_service_schema(
                {
                    vol.Optional("start_message"): str,
                    vol.Optional("start_media_id"): _media_id_validator,
                    vol.Optional("preannounce"): bool,
                    vol.Optional("preannounce_media_id"): _media_id_validator,
                    vol.Optional("extra_system_prompt"): str,
                }
            ),
            cv.has_at_least_one_key("start_message", "start_media_id"),
        ),
        "async_internal_start_conversation",
        [AssistSatelliteEntityFeature.START_CONVERSATION],
    )

    async def handle_ask_question(call: ServiceCall) -> dict[str, Any]:
        """Handle a Show View service call."""
        satellite_entity_id: str = call.data[ATTR_ENTITY_ID]
        satellite_entity: AssistSatelliteEntity | None = component.get_entity(
            satellite_entity_id
        )
        if satellite_entity is None:
            raise HomeAssistantError(
                f"Invalid Assist satellite entity id: {satellite_entity_id}"
            )

        ask_question_args = {
            "question": call.data.get("question"),
            "question_media_id": call.data.get("question_media_id"),
            "preannounce": call.data.get("preannounce", False),
            "answers": call.data.get("answers"),
        }

        if preannounce_media_id := call.data.get("preannounce_media_id"):
            ask_question_args["preannounce_media_id"] = preannounce_media_id

        answer = await satellite_entity.async_internal_ask_question(**ask_question_args)

        if answer is None:
            raise HomeAssistantError("No answer from satellite")

        return asdict(answer)

    hass.services.async_register(
        domain=DOMAIN,
        service="ask_question",
        service_func=handle_ask_question,
        schema=vol.All(
            {
                vol.Required(ATTR_ENTITY_ID): cv.entity_domain(DOMAIN),
                vol.Optional("question"): str,
                vol.Optional("question_media_id"): _media_id_validator,
                vol.Optional("preannounce"): bool,
                vol.Optional("preannounce_media_id"): _media_id_validator,
                vol.Optional("answers"): [
                    {
                        vol.Required("id"): str,
                        vol.Required("sentences"): vol.All(
                            cv.ensure_list,
                            [cv.string],
                            has_one_non_empty_item,
                            has_no_punctuation,
                        ),
                    }
                ],
            },
            cv.has_at_least_one_key("question", "question_media_id"),
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.data[CONNECTION_TEST_DATA] = {}
    async_register_websocket_api(hass)
    hass.http.register_view(ConnectionTestView())

    # Default preannounce sound
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                PREANNOUNCE_URL, str(Path(__file__).parent / PREANNOUNCE_FILENAME)
            )
        ]
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


def has_no_punctuation(value: list[str]) -> list[str]:
    """Validate result does not contain punctuation."""
    for sentence in value:
        if (
            PUNCTUATION_START.search(sentence)
            or PUNCTUATION_END.search(sentence)
            or PUNCTUATION_START_WORD.search(sentence)
            or PUNCTUATION_END_WORD.search(sentence)
        ):
            raise vol.Invalid("sentence should not contain punctuation")

    return value


def has_one_non_empty_item(value: list[str]) -> list[str]:
    """Validate result has at least one item."""
    if len(value) < 1:
        raise vol.Invalid("at least one sentence is required")

    for sentence in value:
        if not sentence:
            raise vol.Invalid("sentences cannot be empty")

    return value


# Validator for media_id fields that accepts both string and media selector format
_media_id_validator = vol.Any(
    cv.string,  # Plain string format
    vol.All(
        vol.Schema(
            {
                vol.Required("media_content_id"): cv.string,
                vol.Required("media_content_type"): cv.string,
                vol.Remove("metadata"): dict,  # Ignore metadata if present
            }
        ),
        # Extract media_content_id from media selector format
        lambda x: x["media_content_id"],
    ),
)
