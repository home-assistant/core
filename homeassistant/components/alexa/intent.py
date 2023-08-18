"""Support for Alexa skill service end point."""
import enum
import logging
from typing import Any

from aiohttp.web import Response

from homeassistant.components import http
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent
from homeassistant.util.decorator import Registry

from .const import DOMAIN, SYN_RESOLUTION_MATCH

_LOGGER = logging.getLogger(__name__)

HANDLERS = Registry()  # type: ignore[var-annotated]

INTENTS_API_ENDPOINT = "/api/alexa"


class SpeechType(enum.StrEnum):
    """The Alexa speech types."""

    plaintext = "PlainText"
    ssml = "SSML"


SPEECH_MAPPINGS = {"plain": SpeechType.plaintext, "ssml": SpeechType.ssml}


class CardType(enum.StrEnum):
    """The Alexa card types."""

    simple = "Simple"
    link_account = "LinkAccount"


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Activate Alexa component."""
    hass.http.register_view(AlexaIntentsView)


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Do intents setup.

    Right now this module does not expose any, but the intent component breaks
    without it.
    """
    pass  # pylint: disable=unnecessary-pass


class UnknownRequest(HomeAssistantError):
    """When an unknown Alexa request is passed in."""


class AlexaIntentsView(http.HomeAssistantView):
    """Handle Alexa requests."""

    url = INTENTS_API_ENDPOINT
    name = "api:alexa"

    async def post(self, request: http.HomeAssistantRequest) -> Response | bytes:
        """Handle Alexa."""
        hass: HomeAssistant = request.app["hass"]
        message: dict[str, Any] = await request.json()

        _LOGGER.debug("Received Alexa request: %s", message)

        try:
            response: dict[str, Any] = await async_handle_message(hass, message)
            return b"" if response is None else self.json(response)
        except UnknownRequest as err:
            _LOGGER.warning(str(err))
            return self.json(intent_error_response(hass, message, str(err)))

        except intent.UnknownIntent as err:
            _LOGGER.warning(str(err))
            return self.json(
                intent_error_response(
                    hass,
                    message,
                    "This intent is not yet configured within Home Assistant.",
                )
            )

        except intent.InvalidSlotInfo as err:
            _LOGGER.error("Received invalid slot data from Alexa: %s", err)
            return self.json(
                intent_error_response(
                    hass, message, "Invalid slot information received for this intent."
                )
            )

        except intent.IntentError as err:
            _LOGGER.exception(str(err))
            return self.json(
                intent_error_response(hass, message, "Error handling intent.")
            )


def intent_error_response(
    hass: HomeAssistant, message: dict[str, Any], error: str
) -> dict[str, Any]:
    """Return an Alexa response that will speak the error message."""
    alexa_intent_info = message["request"].get("intent")
    alexa_response = AlexaIntentResponse(hass, alexa_intent_info)
    alexa_response.add_speech(SpeechType.plaintext, error)
    return alexa_response.as_dict()


async def async_handle_message(
    hass: HomeAssistant, message: dict[str, Any]
) -> dict[str, Any]:
    """Handle an Alexa intent.

    Raises:
     - UnknownRequest
     - intent.UnknownIntent
     - intent.InvalidSlotInfo
     - intent.IntentError

    """
    req = message["request"]
    req_type = req["type"]

    if not (handler := HANDLERS.get(req_type)):
        raise UnknownRequest(f"Received unknown request {req_type}")

    response: dict[str, Any] = await handler(hass, message)
    return response


@HANDLERS.register("SessionEndedRequest")
@HANDLERS.register("IntentRequest")
@HANDLERS.register("LaunchRequest")
async def async_handle_intent(
    hass: HomeAssistant, message: dict[str, Any]
) -> dict[str, Any]:
    """Handle an intent request.

    Raises:
     - intent.UnknownIntent
     - intent.InvalidSlotInfo
     - intent.IntentError

    """
    req = message["request"]
    alexa_intent_info = req.get("intent")
    alexa_response = AlexaIntentResponse(hass, alexa_intent_info)

    if req["type"] == "LaunchRequest":
        intent_name = (
            message.get("session", {}).get("application", {}).get("applicationId")
        )
    elif req["type"] == "SessionEndedRequest":
        app_id = message.get("session", {}).get("application", {}).get("applicationId")
        intent_name = f"{app_id}.{req['type']}"
        alexa_response.variables["reason"] = req["reason"]
        alexa_response.variables["error"] = req.get("error")
    else:
        intent_name = alexa_intent_info["name"]

    intent_response = await intent.async_handle(
        hass,
        DOMAIN,
        intent_name,
        {key: {"value": value} for key, value in alexa_response.variables.items()},
    )

    for intent_speech, alexa_speech in SPEECH_MAPPINGS.items():
        if intent_speech in intent_response.speech:
            alexa_response.add_speech(
                alexa_speech, intent_response.speech[intent_speech]["speech"]
            )
        if intent_speech in intent_response.reprompt:
            alexa_response.add_reprompt(
                alexa_speech, intent_response.reprompt[intent_speech]["reprompt"]
            )

    if "simple" in intent_response.card:
        alexa_response.add_card(
            CardType.simple,
            intent_response.card["simple"]["title"],
            intent_response.card["simple"]["content"],
        )

    return alexa_response.as_dict()


def resolve_slot_data(key: str, request: dict[str, Any]) -> dict[str, str]:
    """Check slot request for synonym resolutions."""
    # Default to the spoken slot value if more than one or none are found. Always
    # passes the id and name of the nearest possible slot resolution. For
    # reference to the request object structure, see the Alexa docs:
    # https://tinyurl.com/ybvm7jhs
    resolved_data: dict[str, Any] = {}
    resolved_data["value"] = request["value"]
    resolved_data["id"] = ""

    if (
        "resolutions" in request
        and "resolutionsPerAuthority" in request["resolutions"]
        and len(request["resolutions"]["resolutionsPerAuthority"]) >= 1
    ):
        # Extract all of the possible values from each authority with a
        # successful match
        possible_values = []

        for entry in request["resolutions"]["resolutionsPerAuthority"]:
            if entry["status"]["code"] != SYN_RESOLUTION_MATCH:
                continue

            possible_values.extend([item["value"] for item in entry["values"]])

        # Always set id if available, otherwise an empty string is used as id
        if len(possible_values) >= 1:
            # Set ID if available
            if "id" in possible_values[0]:
                resolved_data["id"] = possible_values[0]["id"]

        # If there is only one match use the resolved value, otherwise the
        # resolution cannot be determined, so use the spoken slot value and empty string as id
        if len(possible_values) == 1:
            resolved_data["value"] = possible_values[0]["name"]
        else:
            _LOGGER.debug(
                "Found multiple synonym resolutions for slot value: {%s: %s}",
                key,
                resolved_data["value"],
            )

    return resolved_data


class AlexaIntentResponse:
    """Help generating the response for Alexa."""

    def __init__(self, hass: HomeAssistant, intent_info: dict[str, Any] | None) -> None:
        """Initialize the response."""
        self.hass = hass
        self.speech: dict[str, Any] | None = None
        self.card: dict[str, Any] | None = None
        self.reprompt: dict[str, Any] | None = None
        self.session_attributes: dict[str, Any] = {}
        self.should_end_session = True
        self.variables: dict[str, Any] = {}

        # Intent is None if request was a LaunchRequest or SessionEndedRequest
        if intent_info is not None:
            for key, value in intent_info.get("slots", {}).items():
                # Only include slots with values
                if "value" not in value:
                    continue

                _key = key.replace(".", "_")
                _slot_data = resolve_slot_data(key, value)

                self.variables[_key] = _slot_data["value"]
                self.variables[_key + "_Id"] = _slot_data["id"]

    def add_card(self, card_type: CardType, title: str, content: str) -> None:
        """Add a card to the response."""
        assert self.card is None

        card = {"type": card_type.value}

        if card_type == CardType.link_account:
            self.card = card
            return

        card["title"] = title
        card["content"] = content
        self.card = card

    def add_speech(self, speech_type: SpeechType, text: str) -> None:
        """Add speech to the response."""
        assert self.speech is None

        key = "ssml" if speech_type == SpeechType.ssml else "text"

        self.speech = {"type": speech_type.value, key: text}

    def add_reprompt(self, speech_type: SpeechType, text: str) -> None:
        """Add reprompt if user does not answer."""
        assert self.reprompt is None

        key = "ssml" if speech_type == SpeechType.ssml else "text"

        self.should_end_session = False

        self.reprompt = {"type": speech_type.value, key: text}

    def as_dict(self) -> dict[str, Any]:
        """Return response in an Alexa valid dict."""
        response: dict[str, Any] = {"shouldEndSession": self.should_end_session}

        if self.card is not None:
            response["card"] = self.card

        if self.speech is not None:
            response["outputSpeech"] = self.speech

        if self.reprompt is not None:
            response["reprompt"] = {"outputSpeech": self.reprompt}

        return {
            "version": "1.0",
            "sessionAttributes": self.session_attributes,
            "response": response,
        }
