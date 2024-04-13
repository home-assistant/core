"""Support for Google Assistant Smart Home API."""

import asyncio
from collections.abc import Callable, Coroutine
from itertools import product
import logging
import pprint
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID, __version__
from homeassistant.core import HomeAssistant
from homeassistant.helpers import instance_id
from homeassistant.util.decorator import Registry

from .const import (
    ERR_DEVICE_OFFLINE,
    ERR_PROTOCOL_ERROR,
    ERR_UNKNOWN_ERROR,
    EVENT_COMMAND_RECEIVED,
    EVENT_QUERY_RECEIVED,
    EVENT_SYNC_RECEIVED,
)
from .data_redaction import async_redact_msg
from .error import SmartHomeError
from .helpers import GoogleEntity, RequestData, async_get_entities

EXECUTE_LIMIT = 2  # Wait 2 seconds for execute to finish

HANDLERS: Registry[
    str,
    Callable[
        [HomeAssistant, RequestData, dict[str, Any]],
        Coroutine[Any, Any, dict[str, Any] | None],
    ],
] = Registry()
_LOGGER = logging.getLogger(__name__)


async def async_handle_message(
    hass, config, agent_user_id, local_user_id, message, source
):
    """Handle incoming API messages."""
    if _LOGGER.isEnabledFor(logging.DEBUG):
        _LOGGER.debug(
            "Processing message:\n%s",
            pprint.pformat(async_redact_msg(message, agent_user_id)),
        )

    data = RequestData(
        config, local_user_id, source, message["requestId"], message.get("devices")
    )

    response = await _process(hass, data, message)
    if _LOGGER.isEnabledFor(logging.DEBUG):
        if response:
            _LOGGER.debug(
                "Response:\n%s",
                pprint.pformat(async_redact_msg(response["payload"], agent_user_id)),
            )
        else:
            _LOGGER.debug("Empty response")

    if response and "errorCode" in response["payload"]:
        _LOGGER.error(
            "Error handling message\n:%s\nResponse:\n%s",
            pprint.pformat(async_redact_msg(message, agent_user_id)),
            pprint.pformat(async_redact_msg(response["payload"], agent_user_id)),
        )

    return response


async def _process(hass, data, message):
    """Process a message."""
    inputs: list = message.get("inputs")

    if len(inputs) != 1:
        return {
            "requestId": data.request_id,
            "payload": {"errorCode": ERR_PROTOCOL_ERROR},
        }

    if (handler := HANDLERS.get(inputs[0].get("intent"))) is None:
        return {
            "requestId": data.request_id,
            "payload": {"errorCode": ERR_PROTOCOL_ERROR},
        }

    try:
        result = await handler(hass, data, inputs[0].get("payload"))
    except SmartHomeError as err:
        return {"requestId": data.request_id, "payload": {"errorCode": err.code}}
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected error")
        return {
            "requestId": data.request_id,
            "payload": {"errorCode": ERR_UNKNOWN_ERROR},
        }

    if result is None:
        return None

    return {"requestId": data.request_id, "payload": result}


async def async_devices_sync_response(hass, config, agent_user_id):
    """Generate the device serialization."""
    entities = async_get_entities(hass, config)
    instance_uuid = await instance_id.async_get(hass)
    devices = []

    for entity in entities:
        if not entity.should_expose():
            continue

        try:
            devices.append(entity.sync_serialize(agent_user_id, instance_uuid))
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error serializing %s", entity.entity_id)

    return devices


@HANDLERS.register("action.devices.SYNC")
async def async_devices_sync(
    hass: HomeAssistant, data: RequestData, payload: dict[str, Any]
) -> dict[str, Any]:
    """Handle action.devices.SYNC request.

    https://developers.google.com/assistant/smarthome/develop/process-intents#SYNC
    """
    hass.bus.async_fire(
        EVENT_SYNC_RECEIVED,
        {"request_id": data.request_id, "source": data.source},
        context=data.context,
    )

    agent_user_id = data.config.get_agent_user_id_from_context(data.context)
    await data.config.async_connect_agent_user(agent_user_id)

    devices = await async_devices_sync_response(hass, data.config, agent_user_id)
    return create_sync_response(agent_user_id, devices)


@HANDLERS.register("action.devices.QUERY")
async def async_devices_query(
    hass: HomeAssistant, data: RequestData, payload: dict[str, Any]
) -> dict[str, Any]:
    """Handle action.devices.QUERY request.

    https://developers.google.com/assistant/smarthome/develop/process-intents#QUERY
    """
    payload_devices = payload.get("devices", [])

    hass.bus.async_fire(
        EVENT_QUERY_RECEIVED,
        {
            "request_id": data.request_id,
            ATTR_ENTITY_ID: [device["id"] for device in payload_devices],
            "source": data.source,
        },
        context=data.context,
    )

    return await async_devices_query_response(hass, data.config, payload_devices)


async def async_devices_query_response(hass, config, payload_devices):
    """Generate the device serialization."""
    devices = {}
    for device in payload_devices:
        devid = device["id"]

        if not (state := hass.states.get(devid)):
            # If we can't find a state, the device is offline
            devices[devid] = {"online": False}
            continue

        entity = GoogleEntity(hass, config, state)
        try:
            devices[devid] = entity.query_serialize()
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error serializing query for %s", state)
            devices[devid] = {"online": False}

    return {"devices": devices}


async def _entity_execute(entity, data, executions):
    """Execute all commands for an entity.

    Returns a dict if a special result needs to be set.
    """
    for execution in executions:
        try:
            await entity.execute(data, execution)
        except SmartHomeError as err:
            return {
                "ids": [entity.entity_id],
                "status": "ERROR",
                **err.to_response(),
            }

    return None


@HANDLERS.register("action.devices.EXECUTE")
async def handle_devices_execute(
    hass: HomeAssistant, data: RequestData, payload: dict[str, Any]
) -> dict[str, Any]:
    """Handle action.devices.EXECUTE request.

    https://developers.google.com/assistant/smarthome/develop/process-intents#EXECUTE
    """
    entities: dict[str, GoogleEntity] = {}
    executions: dict[str, list[Any]] = {}
    results: dict[str, dict[str, Any]] = {}

    for command in payload["commands"]:
        hass.bus.async_fire(
            EVENT_COMMAND_RECEIVED,
            {
                "request_id": data.request_id,
                ATTR_ENTITY_ID: [device["id"] for device in command["devices"]],
                "execution": command["execution"],
                "source": data.source,
            },
            context=data.context,
        )

        for device, execution in product(command["devices"], command["execution"]):
            entity_id = device["id"]

            # Happens if error occurred. Skip entity for further processing
            if entity_id in results:
                continue

            if entity_id in entities:
                executions[entity_id].append(execution)
                continue

            if (state := hass.states.get(entity_id)) is None:
                results[entity_id] = {
                    "ids": [entity_id],
                    "status": "ERROR",
                    "errorCode": ERR_DEVICE_OFFLINE,
                }
                continue

            entities[entity_id] = GoogleEntity(hass, data.config, state)
            executions[entity_id] = [execution]

    try:
        execute_results = await asyncio.wait_for(
            asyncio.shield(
                asyncio.gather(
                    *(
                        _entity_execute(entities[entity_id], data, execution)
                        for entity_id, execution in executions.items()
                    )
                )
            ),
            EXECUTE_LIMIT,
        )
        for entity_id, result in zip(executions, execute_results, strict=False):
            if result is not None:
                results[entity_id] = result
    except TimeoutError:
        pass

    final_results = list(results.values())

    for entity in entities.values():
        if entity.entity_id in results:
            continue

        entity.async_update()

        final_results.append(
            {
                "ids": [entity.entity_id],
                "status": "SUCCESS",
                "states": entity.query_serialize(),
            }
        )

    return {"commands": final_results}


@HANDLERS.register("action.devices.DISCONNECT")
async def async_devices_disconnect(
    hass: HomeAssistant, data: RequestData, payload: dict[str, Any]
) -> None:
    """Handle action.devices.DISCONNECT request.

    https://developers.google.com/assistant/smarthome/develop/process-intents#DISCONNECT
    """
    assert data.context.user_id is not None
    await data.config.async_disconnect_agent_user(data.context.user_id)


@HANDLERS.register("action.devices.IDENTIFY")
async def async_devices_identify(
    hass: HomeAssistant, data: RequestData, payload: dict[str, Any]
) -> dict[str, Any]:
    """Handle action.devices.IDENTIFY request.

    https://developers.google.com/assistant/smarthome/develop/local#implement_the_identify_handler
    """
    return {
        "device": {
            "id": data.config.get_agent_user_id_from_context(data.context),
            "isLocalOnly": True,
            "isProxy": True,
            "deviceInfo": {
                "hwVersion": "UNKNOWN_HW_VERSION",
                "manufacturer": "Home Assistant",
                "model": "Home Assistant",
                "swVersion": __version__,
            },
        }
    }


@HANDLERS.register("action.devices.REACHABLE_DEVICES")
async def async_devices_reachable(
    hass: HomeAssistant, data: RequestData, payload: dict[str, Any]
) -> dict[str, Any]:
    """Handle action.devices.REACHABLE_DEVICES request.

    https://developers.google.com/assistant/smarthome/develop/local#implement_the_reachable_devices_handler_hub_integrations_only
    """
    google_ids = {dev["id"] for dev in (data.devices or [])}

    return {
        "devices": [
            entity.reachable_device_serialize()
            for entity in async_get_entities(hass, data.config)
            if entity.entity_id in google_ids and entity.should_expose_local()
        ]
    }


@HANDLERS.register("action.devices.PROXY_SELECTED")
async def async_devices_proxy_selected(
    hass: HomeAssistant, data: RequestData, payload: dict[str, Any]
) -> dict[str, Any]:
    """Handle action.devices.PROXY_SELECTED request.

    When selected for local SDK.
    """
    return {}


def create_sync_response(agent_user_id: str, devices: list):
    """Return an empty sync response."""
    return {
        "agentUserId": agent_user_id,
        "devices": devices,
    }


def api_disabled_response(message, agent_user_id):
    """Return a device turned off response."""
    inputs: list = message.get("inputs")

    if inputs and inputs[0].get("intent") == "action.devices.SYNC":
        payload = create_sync_response(agent_user_id, [])
    else:
        payload = {"errorCode": "deviceTurnedOff"}

    return {
        "requestId": message.get("requestId"),
        "payload": payload,
    }
