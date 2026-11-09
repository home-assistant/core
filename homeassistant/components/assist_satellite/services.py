"""Services for the Assist satellite integration."""

from dataclasses import asdict
import re
from typing import Any

from hassil.parse_expression import parse_sentence
from hassil.parser import ParseError
from hassil.util import (
    PUNCTUATION_END,
    PUNCTUATION_END_WORD,
    PUNCTUATION_START,
    PUNCTUATION_START_WORD,
)
import probatio

from homeassistant.auth.permissions.const import CAT_ENTITIES, POLICY_CONTROL
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
    UnknownUser,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    DATA_COMPONENT,
    DOMAIN,
    AssistSatelliteEntityFeature,
    AssistSatelliteService,
    AssistSatelliteServiceArgument,
)
from .entity import AssistSatelliteEntity


def has_no_punctuation(value: list[str]) -> list[str]:
    """Validate result does not contain punctuation."""
    for sentence in value:
        # Exclude {list_references} which may contain punctuation characters.
        sentence = _remove_list_references(sentence)
        if (
            PUNCTUATION_START.search(sentence)
            or PUNCTUATION_END.search(sentence)
            or PUNCTUATION_START_WORD.search(sentence)
            or PUNCTUATION_END_WORD.search(sentence)
        ):
            raise probatio.Invalid("sentence should not contain punctuation")

    return value


def _remove_list_references(sentence: str) -> str:
    """Remove {list_references} from a sentence for linting."""
    return re.sub(r"(?<!\\)\{[^{}]*\}", "", sentence)


def is_valid_sentence(value: list[str]) -> list[str]:
    """Validate result can be parsed by hassil."""
    for sentence in value:
        try:
            parse_sentence(sentence)
        except ParseError as err:
            raise probatio.Invalid(f"invalid sentence: {err}") from err
    return value


def has_one_non_empty_item(value: list[str]) -> list[str]:
    """Validate result has at least one item."""
    if len(value) < 1:
        raise probatio.Invalid("at least one sentence is required")

    for sentence in value:
        if not sentence:
            raise probatio.Invalid("sentences cannot be empty")

    return value


# Validator for media_id fields that accepts both string and media selector format
_media_id_validator = probatio.Any(
    cv.string,  # Plain string format
    probatio.All(
        probatio.Schema(
            {
                probatio.Required("media_content_id"): cv.string,
                probatio.Required("media_content_type"): cv.string,
                probatio.Remove("metadata"): dict,  # Ignore metadata if present
            }
        ),
        # Extract media_content_id from media selector format
        lambda x: x["media_content_id"],
    ),
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Assist satellite services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        AssistSatelliteService.ANNOUNCE,
        probatio.All(
            cv.make_entity_service_schema(
                {
                    probatio.Optional(AssistSatelliteServiceArgument.MESSAGE): str,
                    probatio.Optional(
                        AssistSatelliteServiceArgument.MEDIA_ID
                    ): _media_id_validator,
                    probatio.Optional(
                        AssistSatelliteServiceArgument.PREANNOUNCE, default=True
                    ): bool,
                    probatio.Optional(
                        AssistSatelliteServiceArgument.PREANNOUNCE_MEDIA_ID
                    ): _media_id_validator,
                }
            ),
            probatio.AtLeastOne(
                AssistSatelliteServiceArgument.MESSAGE.value,
                AssistSatelliteServiceArgument.MEDIA_ID.value,
            ),
        ),
        "async_internal_announce",
        [AssistSatelliteEntityFeature.ANNOUNCE],
    )

    component.async_register_entity_service(
        AssistSatelliteService.START_CONVERSATION,
        probatio.All(
            cv.make_entity_service_schema(
                {
                    probatio.Optional(
                        AssistSatelliteServiceArgument.START_MESSAGE
                    ): str,
                    probatio.Optional(
                        AssistSatelliteServiceArgument.START_MEDIA_ID
                    ): _media_id_validator,
                    probatio.Optional(
                        AssistSatelliteServiceArgument.PREANNOUNCE, default=True
                    ): bool,
                    probatio.Optional(
                        AssistSatelliteServiceArgument.PREANNOUNCE_MEDIA_ID
                    ): _media_id_validator,
                    probatio.Optional(
                        AssistSatelliteServiceArgument.EXTRA_SYSTEM_PROMPT
                    ): str,
                }
            ),
            probatio.AtLeastOne(
                AssistSatelliteServiceArgument.START_MESSAGE.value,
                AssistSatelliteServiceArgument.START_MEDIA_ID.value,
            ),
        ),
        "async_internal_start_conversation",
        [AssistSatelliteEntityFeature.START_CONVERSATION],
    )

    async def handle_ask_question(call: ServiceCall) -> dict[str, Any]:
        """Handle a Show View service call."""
        satellite_entity_id: str = call.data[AssistSatelliteServiceArgument.ENTITY_ID]
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None:
                raise UnknownUser(
                    context=call.context,
                    permission=POLICY_CONTROL,
                    user_id=call.context.user_id,
                )
            if not user.permissions.check_entity(satellite_entity_id, POLICY_CONTROL):
                raise Unauthorized(
                    context=call.context,
                    permission=POLICY_CONTROL,
                    user_id=call.context.user_id,
                    perm_category=CAT_ENTITIES,
                )

        satellite_entity: AssistSatelliteEntity | None = component.get_entity(
            satellite_entity_id
        )
        if satellite_entity is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_entity_id",
                translation_placeholders={"entity_id": satellite_entity_id},
            )

        satellite_entity.async_set_context(call.context)

        ask_question_args = {
            "question": call.data.get(AssistSatelliteServiceArgument.QUESTION),
            "question_media_id": call.data.get(
                AssistSatelliteServiceArgument.QUESTION_MEDIA_ID
            ),
            "preannounce": call.data.get(
                AssistSatelliteServiceArgument.PREANNOUNCE, True
            ),
            "answers": call.data.get(AssistSatelliteServiceArgument.ANSWERS),
        }

        if preannounce_media_id := call.data.get(
            AssistSatelliteServiceArgument.PREANNOUNCE_MEDIA_ID
        ):
            ask_question_args["preannounce_media_id"] = preannounce_media_id

        answer = await satellite_entity.async_internal_ask_question(**ask_question_args)

        if answer is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_answer",
            )

        return asdict(answer)

    hass.services.async_register(
        domain=DOMAIN,
        service=AssistSatelliteService.ASK_QUESTION,
        service_func=handle_ask_question,
        schema=probatio.All(
            {
                probatio.Required(
                    AssistSatelliteServiceArgument.ENTITY_ID
                ): cv.entity_domain(DOMAIN),
                probatio.Optional(AssistSatelliteServiceArgument.QUESTION): str,
                probatio.Optional(
                    AssistSatelliteServiceArgument.QUESTION_MEDIA_ID
                ): _media_id_validator,
                probatio.Optional(
                    AssistSatelliteServiceArgument.PREANNOUNCE, default=True
                ): bool,
                probatio.Optional(
                    AssistSatelliteServiceArgument.PREANNOUNCE_MEDIA_ID
                ): _media_id_validator,
                probatio.Optional(AssistSatelliteServiceArgument.ANSWERS): [
                    {
                        probatio.Required("id"): str,
                        probatio.Required("sentences"): probatio.All(
                            probatio.EnsureList(),
                            [cv.string],
                            has_one_non_empty_item,
                            has_no_punctuation,
                            is_valid_sentence,
                        ),
                    }
                ],
            },
            probatio.AtLeastOne(
                AssistSatelliteServiceArgument.QUESTION.value,
                AssistSatelliteServiceArgument.QUESTION_MEDIA_ID.value,
            ),
        ),
        supports_response=SupportsResponse.ONLY,
    )
