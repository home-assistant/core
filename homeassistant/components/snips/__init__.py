"""Support for Snips on-device ASR and NLU."""
from datetime import timedelta
import json
import logging

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.helpers.typing import ConfigType

DOMAIN = "snips"
CONF_INTENTS = "intents"
CONF_ACTION = "action"
CONF_FEEDBACK = "feedback_sounds"
CONF_PROBABILITY = "probability_threshold"
CONF_SITE_IDS = "site_ids"

SERVICE_SAY = "say"
SERVICE_SAY_ACTION = "say_action"
SERVICE_FEEDBACK_ON = "feedback_on"
SERVICE_FEEDBACK_OFF = "feedback_off"

INTENT_TOPIC = "hermes/intent/#"
FEEDBACK_ON_TOPIC = "hermes/feedback/sound/toggleOn"
FEEDBACK_OFF_TOPIC = "hermes/feedback/sound/toggleOff"

ATTR_TEXT = "text"
ATTR_SITE_ID = "site_id"
ATTR_CUSTOM_DATA = "custom_data"
ATTR_CAN_BE_ENQUEUED = "can_be_enqueued"
ATTR_INTENT_FILTER = "intent_filter"

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_FEEDBACK): cv.boolean,
                vol.Optional(CONF_PROBABILITY, default=0): vol.Coerce(float),
                vol.Optional(CONF_SITE_IDS, default=["default"]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

INTENT_SCHEMA = vol.Schema(
    {
        vol.Required("input"): str,
        vol.Required("intent"): {vol.Required("intentName"): str},
        vol.Optional("slots"): [
            {
                vol.Required("slotName"): str,
                vol.Required("value"): {
                    vol.Required("kind"): str,
                    vol.Optional("value"): cv.match_all,
                    vol.Optional("rawValue"): cv.match_all,
                },
            }
        ],
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA_SAY = vol.Schema(
    {
        vol.Required(ATTR_TEXT): str,
        vol.Optional(ATTR_SITE_ID, default="default"): str,
        vol.Optional(ATTR_CUSTOM_DATA, default=""): str,
    }
)
SERVICE_SCHEMA_SAY_ACTION = vol.Schema(
    {
        vol.Required(ATTR_TEXT): str,
        vol.Optional(ATTR_SITE_ID, default="default"): str,
        vol.Optional(ATTR_CUSTOM_DATA, default=""): str,
        vol.Optional(ATTR_CAN_BE_ENQUEUED, default=True): cv.boolean,
        vol.Optional(ATTR_INTENT_FILTER): vol.All(cv.ensure_list),
    }
)
SERVICE_SCHEMA_FEEDBACK = vol.Schema(
    {vol.Optional(ATTR_SITE_ID, default="default"): str}
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Activate Snips component."""
    # Make sure MQTT is available and the entry is loaded
    if not hass.config_entries.async_entries(
        mqtt.DOMAIN
    ) or not await hass.config_entries.async_wait_component(
        hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    ):
        _LOGGER.error("MQTT integration is not available")
        return False

    async def async_set_feedback(site_ids, state):
        """Set Feedback sound state."""
        site_ids = site_ids if site_ids else config[DOMAIN].get(CONF_SITE_IDS)
        topic = FEEDBACK_ON_TOPIC if state else FEEDBACK_OFF_TOPIC
        for site_id in site_ids:
            payload = json.dumps({"siteId": site_id})
            await mqtt.async_publish(hass, FEEDBACK_ON_TOPIC, "", qos=0, retain=False)
            await mqtt.async_publish(hass, topic, payload, qos=int(state), retain=state)

    if CONF_FEEDBACK in config[DOMAIN]:
        await async_set_feedback(None, config[DOMAIN][CONF_FEEDBACK])

    async def message_received(msg):
        """Handle new messages on MQTT."""
        _LOGGER.debug("New intent: %s", msg.payload)

        try:
            request = json.loads(msg.payload)
        except TypeError:
            _LOGGER.error("Received invalid JSON: %s", msg.payload)
            return

        if request["intent"]["confidenceScore"] < config[DOMAIN].get(CONF_PROBABILITY):
            _LOGGER.warning(
                "Intent below probaility threshold %s < %s",
                request["intent"]["confidenceScore"],
                config[DOMAIN].get(CONF_PROBABILITY),
            )
            return

        try:
            request = INTENT_SCHEMA(request)
        except vol.Invalid as err:
            _LOGGER.error("Intent has invalid schema: %s. %s", err, request)
            return

        if request["intent"]["intentName"].startswith("user_"):
            intent_type = request["intent"]["intentName"].split("__")[-1]
        else:
            intent_type = request["intent"]["intentName"].split(":")[-1]
        slots = {}
        for slot in request.get("slots", []):
            slots[slot["slotName"]] = {"value": resolve_slot_values(slot)}
            slots["{}_raw".format(slot["slotName"])] = {"value": slot["rawValue"]}
        slots["site_id"] = {"value": request.get("siteId")}
        slots["session_id"] = {"value": request.get("sessionId")}
        slots["confidenceScore"] = {"value": request["intent"]["confidenceScore"]}

        try:
            intent_response = await intent.async_handle(
                hass, DOMAIN, intent_type, slots, request["input"]
            )
            notification = {"sessionId": request.get("sessionId", "default")}

            if "plain" in intent_response.speech:
                notification["text"] = intent_response.speech["plain"]["speech"]

            _LOGGER.debug("send_response %s", json.dumps(notification))
            await mqtt.async_publish(
                hass, "hermes/dialogueManager/endSession", json.dumps(notification)
            )
        except intent.UnknownIntent:
            _LOGGER.warning(
                "Received unknown intent %s", request["intent"]["intentName"]
            )
        except intent.IntentError:
            _LOGGER.exception("Error while handling intent: %s", intent_type)

    await mqtt.async_subscribe(hass, INTENT_TOPIC, message_received)

    async def snips_say(call: ServiceCall) -> None:
        """Send a Snips notification message."""
        notification = {
            "siteId": call.data.get(ATTR_SITE_ID, "default"),
            "customData": call.data.get(ATTR_CUSTOM_DATA, ""),
            "init": {"type": "notification", "text": call.data.get(ATTR_TEXT)},
        }
        await mqtt.async_publish(
            hass, "hermes/dialogueManager/startSession", json.dumps(notification)
        )
        return

    async def snips_say_action(call: ServiceCall) -> None:
        """Send a Snips action message."""
        notification = {
            "siteId": call.data.get(ATTR_SITE_ID, "default"),
            "customData": call.data.get(ATTR_CUSTOM_DATA, ""),
            "init": {
                "type": "action",
                "text": call.data.get(ATTR_TEXT),
                "canBeEnqueued": call.data.get(ATTR_CAN_BE_ENQUEUED, True),
                "intentFilter": call.data.get(ATTR_INTENT_FILTER, []),
            },
        }
        await mqtt.async_publish(
            hass, "hermes/dialogueManager/startSession", json.dumps(notification)
        )
        return

    async def feedback_on(call: ServiceCall) -> None:
        """Turn feedback sounds on."""
        await async_set_feedback(call.data.get(ATTR_SITE_ID), True)

    async def feedback_off(call: ServiceCall) -> None:
        """Turn feedback sounds off."""
        await async_set_feedback(call.data.get(ATTR_SITE_ID), False)

    hass.services.async_register(
        DOMAIN, SERVICE_SAY, snips_say, schema=SERVICE_SCHEMA_SAY
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SAY_ACTION, snips_say_action, schema=SERVICE_SCHEMA_SAY_ACTION
    )
    hass.services.async_register(
        DOMAIN, SERVICE_FEEDBACK_ON, feedback_on, schema=SERVICE_SCHEMA_FEEDBACK
    )
    hass.services.async_register(
        DOMAIN, SERVICE_FEEDBACK_OFF, feedback_off, schema=SERVICE_SCHEMA_FEEDBACK
    )

    return True


def resolve_slot_values(slot):
    """Convert snips builtin types to usable values."""
    if "value" in slot["value"]:
        value = slot["value"]["value"]
    else:
        value = slot["rawValue"]

    if slot.get("entity") == "snips/duration":
        delta = timedelta(
            weeks=slot["value"]["weeks"],
            days=slot["value"]["days"],
            hours=slot["value"]["hours"],
            minutes=slot["value"]["minutes"],
            seconds=slot["value"]["seconds"],
        )
        value = delta.total_seconds()

    return value
