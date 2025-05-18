"""Assist satellite Websocket API."""

import asyncio
from dataclasses import asdict, replace
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import uuid as uuid_util

from .connection_test import CONNECTION_TEST_URL_BASE
from .const import (
    CONNECTION_TEST_DATA,
    DATA_COMPONENT,
    DOMAIN,
    AssistSatelliteEntityFeature,
)
from .entity import AssistSatelliteConfiguration

CONNECTION_TEST_TIMEOUT = 30


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the websocket API."""
    websocket_api.async_register_command(hass, websocket_intercept_wake_word)
    websocket_api.async_register_command(hass, websocket_get_configuration)
    websocket_api.async_register_command(hass, websocket_set_wake_words)
    websocket_api.async_register_command(hass, websocket_test_connection)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "assist_satellite/intercept_wake_word",
        vol.Required("entity_id"): cv.entity_domain(DOMAIN),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_intercept_wake_word(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Intercept the next wake word from a satellite."""
    satellite = hass.data[DATA_COMPONENT].get_entity(msg["entity_id"])
    if satellite is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Entity not found"
        )
        return

    async def intercept_wake_word() -> None:
        """Push an intercepted wake word to websocket."""
        try:
            wake_word_phrase = await satellite.async_intercept_wake_word()
            connection.send_message(
                websocket_api.event_message(
                    msg["id"],
                    {"wake_word_phrase": wake_word_phrase},
                )
            )
        except HomeAssistantError as err:
            connection.send_error(msg["id"], "home_assistant_error", str(err))

    task = hass.async_create_task(intercept_wake_word(), "intercept_wake_word")
    connection.subscriptions[msg["id"]] = task.cancel
    connection.send_message(websocket_api.result_message(msg["id"]))


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "assist_satellite/get_configuration",
        vol.Required("entity_id"): cv.entity_domain(DOMAIN),
    }
)
def websocket_get_configuration(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the current satellite configuration."""
    satellite = hass.data[DATA_COMPONENT].get_entity(msg["entity_id"])
    if satellite is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Entity not found"
        )
        return

    try:
        config_dict = asdict(satellite.async_get_configuration())
    except NotImplementedError:
        # Stub configuration
        config_dict = asdict(
            AssistSatelliteConfiguration(
                available_wake_words=[], active_wake_words=[], max_active_wake_words=1
            )
        )

    config_dict["pipeline_entity_id"] = satellite.pipeline_entity_id
    config_dict["vad_entity_id"] = satellite.vad_sensitivity_entity_id

    connection.send_result(msg["id"], config_dict)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "assist_satellite/set_wake_words",
        vol.Required("entity_id"): cv.entity_domain(DOMAIN),
        vol.Required("wake_word_ids"): [str],
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_set_wake_words(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Set the active wake words for the satellite."""
    satellite = hass.data[DATA_COMPONENT].get_entity(msg["entity_id"])
    if satellite is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Entity not found"
        )
        return

    config = satellite.async_get_configuration()

    # Don't set too many active wake words
    actual_ids = msg["wake_word_ids"]
    if len(actual_ids) > config.max_active_wake_words:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_SUPPORTED,
            f"Maximum number of active wake words is {config.max_active_wake_words}",
        )
        return

    # Verify all ids are available
    available_ids = {ww.id for ww in config.available_wake_words}
    for ww_id in actual_ids:
        if ww_id not in available_ids:
            connection.send_error(
                msg["id"],
                websocket_api.ERR_NOT_SUPPORTED,
                f"Wake word id is not supported: {ww_id}",
            )
            return

    await satellite.async_set_configuration(
        replace(config, active_wake_words=actual_ids)
    )
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "assist_satellite/test_connection",
        vol.Required("entity_id"): cv.entity_domain(DOMAIN),
    }
)
@websocket_api.async_response
async def websocket_test_connection(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Test the connection between the device and Home Assistant.

    Send an announcement to the device with a special media id.
    """
    component = hass.data[DATA_COMPONENT]
    satellite = component.get_entity(msg["entity_id"])
    if satellite is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Entity not found"
        )
        return
    if not (satellite.supported_features or 0) & AssistSatelliteEntityFeature.ANNOUNCE:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_SUPPORTED,
            "Entity does not support announce",
        )
        return

    # Announce and wait for event
    connection_test_data = hass.data[CONNECTION_TEST_DATA]
    connection_id = uuid_util.random_uuid_hex()
    connection_test_event = asyncio.Event()
    connection_test_data[connection_id] = connection_test_event

    hass.async_create_background_task(
        satellite.async_internal_announce(
            media_id=f"{CONNECTION_TEST_URL_BASE}/{connection_id}",
            preannounce=False,
        ),
        f"assist_satellite_connection_test_{msg['entity_id']}",
    )

    try:
        async with asyncio.timeout(CONNECTION_TEST_TIMEOUT):
            await connection_test_event.wait()
            connection.send_result(msg["id"], {"status": "success"})
    except TimeoutError:
        connection.send_result(msg["id"], {"status": "timeout"})
    finally:
        connection_test_data.pop(connection_id, None)
