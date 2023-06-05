"""Alexa state report code."""
from __future__ import annotations

import asyncio
from http import HTTPStatus
import json
import logging
from typing import TYPE_CHECKING, cast

import aiohttp
import async_timeout

from homeassistant.const import MATCH_ALL, STATE_ON
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.significant_change import create_checker
import homeassistant.util.dt as dt_util
from homeassistant.util.json import JsonObjectType, json_loads_object

from .const import API_CHANGE, DATE_FORMAT, DOMAIN, Cause
from .entities import ENTITY_ADAPTERS, AlexaEntity, generate_alexa_id
from .errors import NoTokenAvailable, RequireRelink
from .messages import AlexaResponse

if TYPE_CHECKING:
    from .config import AbstractConfig

_LOGGER = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 10


async def async_enable_proactive_mode(hass, smart_home_config):
    """Enable the proactive mode.

    Proactive mode makes this component report state changes to Alexa.
    """
    # Validate we can get access token.
    await smart_home_config.async_get_access_token()

    @callback
    def extra_significant_check(
        hass: HomeAssistant,
        old_state: str,
        old_attrs: dict,
        old_extra_arg: dict,
        new_state: str,
        new_attrs: dict,
        new_extra_arg: dict,
    ):
        """Check if the serialized data has changed."""
        return old_extra_arg is not None and old_extra_arg != new_extra_arg

    checker = await create_checker(hass, DOMAIN, extra_significant_check)

    async def async_entity_state_listener(
        changed_entity: str,
        old_state: State | None,
        new_state: State | None,
    ):
        if not hass.is_running:
            return

        if not new_state:
            return

        if new_state.domain not in ENTITY_ADAPTERS:
            return

        if not smart_home_config.should_expose(changed_entity):
            _LOGGER.debug("Not exposing %s because filtered by config", changed_entity)
            return

        alexa_changed_entity: AlexaEntity = ENTITY_ADAPTERS[new_state.domain](
            hass, smart_home_config, new_state
        )

        # Determine how entity should be reported on
        should_report = False
        should_doorbell = False

        for interface in alexa_changed_entity.interfaces():
            if not should_report and interface.properties_proactively_reported():
                should_report = True

            if interface.name() == "Alexa.DoorbellEventSource":
                should_doorbell = True
                break

        if not should_report and not should_doorbell:
            return

        if should_doorbell:
            if new_state.state == STATE_ON and (
                old_state is None or old_state.state != STATE_ON
            ):
                await async_send_doorbell_event_message(
                    hass, smart_home_config, alexa_changed_entity
                )
            return

        alexa_properties = list(alexa_changed_entity.serialize_properties())

        if not checker.async_is_significant_change(
            new_state, extra_arg=alexa_properties
        ):
            return

        await async_send_changereport_message(
            hass, smart_home_config, alexa_changed_entity, alexa_properties
        )

    return async_track_state_change(hass, MATCH_ALL, async_entity_state_listener)


async def async_send_changereport_message(
    hass, config, alexa_entity, alexa_properties, *, invalidate_access_token=True
):
    """Send a ChangeReport message for an Alexa entity.

    https://developer.amazon.com/docs/smarthome/state-reporting-for-a-smart-home-skill.html#report-state-with-changereport-events
    """
    try:
        token = await config.async_get_access_token()
    except (RequireRelink, NoTokenAvailable):
        await config.set_authorized(False)
        _LOGGER.error(
            "Error when sending ChangeReport to Alexa, could not get access token"
        )
        return

    headers = {"Authorization": f"Bearer {token}"}

    endpoint = alexa_entity.alexa_id()

    payload = {
        API_CHANGE: {
            "cause": {"type": Cause.APP_INTERACTION},
            "properties": alexa_properties,
        }
    }

    message = AlexaResponse(name="ChangeReport", namespace="Alexa", payload=payload)
    message.set_endpoint_full(token, endpoint)

    message_serialized = message.serialize()
    session = async_get_clientsession(hass)

    try:
        async with async_timeout.timeout(DEFAULT_TIMEOUT):
            response = await session.post(
                config.endpoint,
                headers=headers,
                json=message_serialized,
                allow_redirects=True,
            )

    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.error("Timeout sending report to Alexa for %s", alexa_entity.entity_id)
        return

    response_text = await response.text()

    _LOGGER.debug("Sent: %s", json.dumps(message_serialized))
    _LOGGER.debug("Received (%s): %s", response.status, response_text)

    if response.status == HTTPStatus.ACCEPTED:
        return

    response_json = json_loads_object(response_text)
    response_payload = cast(JsonObjectType, response_json["payload"])

    if response_payload["code"] == "INVALID_ACCESS_TOKEN_EXCEPTION":
        if invalidate_access_token:
            # Invalidate the access token and try again
            config.async_invalidate_access_token()
            return await async_send_changereport_message(
                hass,
                config,
                alexa_entity,
                alexa_properties,
                invalidate_access_token=False,
            )
        await config.set_authorized(False)

    _LOGGER.error(
        "Error when sending ChangeReport for %s to Alexa: %s: %s",
        alexa_entity.entity_id,
        response_payload["code"],
        response_payload["description"],
    )


async def async_send_add_or_update_message(
    hass: HomeAssistant, config: AbstractConfig, entity_ids: list[str]
) -> aiohttp.ClientResponse:
    """Send an AddOrUpdateReport message for entities.

    https://developer.amazon.com/docs/device-apis/alexa-discovery.html#add-or-update-report
    """
    token = await config.async_get_access_token()

    headers = {"Authorization": f"Bearer {token}"}

    endpoints = []

    for entity_id in entity_ids:
        if (domain := entity_id.split(".", 1)[0]) not in ENTITY_ADAPTERS:
            continue

        if (state := hass.states.get(entity_id)) is None:
            continue

        alexa_entity = ENTITY_ADAPTERS[domain](hass, config, state)
        endpoints.append(alexa_entity.serialize_discovery())

    payload = {"endpoints": endpoints, "scope": {"type": "BearerToken", "token": token}}

    message = AlexaResponse(
        name="AddOrUpdateReport", namespace="Alexa.Discovery", payload=payload
    )

    message_serialized = message.serialize()
    session = async_get_clientsession(hass)

    return await session.post(
        config.endpoint, headers=headers, json=message_serialized, allow_redirects=True
    )


async def async_send_delete_message(
    hass: HomeAssistant, config: AbstractConfig, entity_ids: list[str]
) -> aiohttp.ClientResponse:
    """Send an DeleteReport message for entities.

    https://developer.amazon.com/docs/device-apis/alexa-discovery.html#deletereport-event
    """
    token = await config.async_get_access_token()

    headers = {"Authorization": f"Bearer {token}"}

    endpoints = []

    for entity_id in entity_ids:
        domain = entity_id.split(".", 1)[0]

        if domain not in ENTITY_ADAPTERS:
            continue

        endpoints.append({"endpointId": generate_alexa_id(entity_id)})

    payload = {"endpoints": endpoints, "scope": {"type": "BearerToken", "token": token}}

    message = AlexaResponse(
        name="DeleteReport", namespace="Alexa.Discovery", payload=payload
    )

    message_serialized = message.serialize()
    session = async_get_clientsession(hass)

    return await session.post(
        config.endpoint, headers=headers, json=message_serialized, allow_redirects=True
    )


async def async_send_doorbell_event_message(hass, config, alexa_entity):
    """Send a DoorbellPress event message for an Alexa entity.

    https://developer.amazon.com/en-US/docs/alexa/device-apis/alexa-doorbelleventsource.html
    """
    token = await config.async_get_access_token()

    headers = {"Authorization": f"Bearer {token}"}

    endpoint = alexa_entity.alexa_id()

    message = AlexaResponse(
        name="DoorbellPress",
        namespace="Alexa.DoorbellEventSource",
        payload={
            "cause": {"type": Cause.PHYSICAL_INTERACTION},
            "timestamp": dt_util.utcnow().strftime(DATE_FORMAT),
        },
    )

    message.set_endpoint_full(token, endpoint)

    message_serialized = message.serialize()
    session = async_get_clientsession(hass)

    try:
        async with async_timeout.timeout(DEFAULT_TIMEOUT):
            response = await session.post(
                config.endpoint,
                headers=headers,
                json=message_serialized,
                allow_redirects=True,
            )

    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.error("Timeout sending report to Alexa for %s", alexa_entity.entity_id)
        return

    response_text = await response.text()

    _LOGGER.debug("Sent: %s", json.dumps(message_serialized))
    _LOGGER.debug("Received (%s): %s", response.status, response_text)

    if response.status == HTTPStatus.ACCEPTED:
        return

    response_json = json_loads_object(response_text)
    response_payload = cast(JsonObjectType, response_json["payload"])

    _LOGGER.error(
        "Error when sending DoorbellPress event for %s to Alexa: %s: %s",
        alexa_entity.entity_id,
        response_payload["code"],
        response_payload["description"],
    )
