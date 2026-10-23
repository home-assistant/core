"""Provide functionality to wake word."""

import asyncio
import logging

import probatio

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .entity import WakeWordDetectionEntity
from .models import DetectionResult, WakeWord

__all__ = [
    "DOMAIN",
    "DetectionResult",
    "WakeWord",
    "WakeWordDetectionEntity",
    "async_default_entity",
    "async_get_wake_word_detection_entity",
]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)
DATA_COMPONENT: HassKey[EntityComponent[WakeWordDetectionEntity]] = HassKey(DOMAIN)

TIMEOUT_FETCH_WAKE_WORDS = 10


@callback
def async_default_entity(hass: HomeAssistant) -> str | None:
    """Return the entity id of the default engine."""
    return next(iter(hass.states.async_entity_ids(DOMAIN)), None)


@callback
def async_get_wake_word_detection_entity(
    hass: HomeAssistant, entity_id: str
) -> WakeWordDetectionEntity | None:
    """Return wake word entity."""
    return hass.data[DATA_COMPONENT].get_entity(entity_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up wake word."""
    websocket_api.async_register_command(hass, websocket_entity_info)

    component = hass.data[DATA_COMPONENT] = EntityComponent[WakeWordDetectionEntity](
        _LOGGER, DOMAIN, hass
    )
    component.register_shutdown()

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up a config entry."""
    if not await hass.data[DATA_COMPONENT].async_setup_entry(entry):
        raise ConfigEntryError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="platform_setup_failed",
            translation_placeholders={"platform": entry.domain, "domain": DOMAIN},
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.data[DATA_COMPONENT].async_unload_entry(entry)


@websocket_api.websocket_command(
    {
        "type": "wake_word/info",
        probatio.Required("entity_id"): cv.entity_domain(DOMAIN),
    }
)
@websocket_api.async_response
async def websocket_entity_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Get info about wake word entity."""
    entity = hass.data[DATA_COMPONENT].get_entity(msg["entity_id"])

    if entity is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Entity not found"
        )
        return

    try:
        async with asyncio.timeout(TIMEOUT_FETCH_WAKE_WORDS):
            wake_words = await entity.get_supported_wake_words()
    except TimeoutError:
        connection.send_error(
            msg["id"], websocket_api.ERR_TIMEOUT, "Timeout fetching wake words"
        )
        return

    connection.send_result(
        msg["id"],
        {"wake_words": wake_words},
    )
