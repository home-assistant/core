"""Provide functionality to wake word."""

from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import AsyncIterable
import logging
from typing import final

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .models import DetectionResult, WakeWord

__all__ = [
    "async_default_entity",
    "async_get_wake_word_detection_entity",
    "DetectionResult",
    "DOMAIN",
    "WakeWord",
    "WakeWordDetectionEntity",
]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

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
    component: EntityComponent[WakeWordDetectionEntity] = hass.data[DOMAIN]

    return component.get_entity(entity_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up wake word."""
    websocket_api.async_register_command(hass, websocket_entity_info)

    component = hass.data[DOMAIN] = EntityComponent(_LOGGER, DOMAIN, hass)
    component.register_shutdown()

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class WakeWordDetectionEntity(RestoreEntity):
    """Represent a single wake word provider."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False
    __last_detected: str | None = None

    @property
    @final
    def state(self) -> str | None:
        """Return the state of the entity."""
        return self.__last_detected

    @abstractmethod
    async def get_supported_wake_words(self) -> list[WakeWord]:
        """Return a list of supported wake words."""

    @abstractmethod
    async def _async_process_audio_stream(
        self, stream: AsyncIterable[tuple[bytes, int]], wake_word_id: str | None
    ) -> DetectionResult | None:
        """Try to detect wake word(s) in an audio stream with timestamps.

        Audio must be 16Khz sample rate with 16-bit mono PCM samples.
        """

    async def async_process_audio_stream(
        self, stream: AsyncIterable[tuple[bytes, int]], wake_word_id: str | None
    ) -> DetectionResult | None:
        """Try to detect wake word(s) in an audio stream with timestamps.

        Audio must be 16Khz sample rate with 16-bit mono PCM samples.
        """
        result = await self._async_process_audio_stream(stream, wake_word_id)
        if result is not None:
            # Update last detected only when there is a detection
            self.__last_detected = dt_util.utcnow().isoformat()
            self.async_write_ha_state()

        return result

    async def async_internal_added_to_hass(self) -> None:
        """Call when the entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if (
            state is not None
            and state.state is not None
            and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ):
            self.__last_detected = state.state


@websocket_api.websocket_command(
    {
        "type": "wake_word/info",
        vol.Required("entity_id"): cv.entity_domain(DOMAIN),
    }
)
@websocket_api.async_response
@callback
async def websocket_entity_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Get info about wake word entity."""
    component: EntityComponent[WakeWordDetectionEntity] = hass.data[DOMAIN]
    entity = component.get_entity(msg["entity_id"])

    if entity is None:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_FOUND, "Entity not found"
        )
        return

    try:
        async with asyncio.timeout(TIMEOUT_FETCH_WAKE_WORDS):
            wake_words = await entity.get_supported_wake_words()
    except TimeoutError:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_TIMEOUT, "Timeout fetching wake words"
        )
        return

    connection.send_result(
        msg["id"],
        {"wake_words": wake_words},
    )
