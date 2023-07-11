"""Provide functionality to WWD."""
from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import AsyncGenerator, AsyncIterable, Callable
from dataclasses import asdict
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .models import DetectionResult, WakeWord

__all__ = [
    "async_default_engine",
    "async_get_wake_word_detection_entity",
    "DetectionResult",
    "DOMAIN",
    "WakeWord",
    "WakeWordDetectionEntity",
]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@callback
def async_default_engine(hass: HomeAssistant) -> str | None:
    """Return the domain or entity id of the default engine."""
    return next(iter(hass.states.async_entity_ids(DOMAIN)), None)


@callback
def async_get_wake_word_detection_entity(
    hass: HomeAssistant, entity_id: str
) -> WakeWordDetectionEntity | None:
    """Return wwd entity."""
    component: EntityComponent = hass.data[DOMAIN]

    return component.get_entity(entity_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up STT."""
    component = hass.data[DOMAIN] = EntityComponent(_LOGGER, DOMAIN, hass)
    component.register_shutdown()

    # Register websocket API
    websocket_api.async_register_command(hass, websocket_detect)
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
    """Represent a single WWD provider."""

    _attr_should_poll = False

    @property
    @abstractmethod
    def supported_wake_words(self) -> list[WakeWord]:
        """Return a list of supported wake words."""

    @abstractmethod
    async def async_process_audio_stream(
        self, stream: AsyncIterable[tuple[bytes, int]]
    ) -> DetectionResult | None:
        """Try to detect wake word(s) in an audio stream with timestamps.

        Audio must be 16Khz sample rate with 16-bit mono PCM samples.
        """


@websocket_api.websocket_command(
    vol.All(
        websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
            {
                vol.Required("type"): "wake/detect",
                vol.Optional("entity_id"): vol.Any(str, None),
                vol.Optional("timestamp_start"): vol.Any(int, None),
            },
        ),
    ),
)
@websocket_api.async_response
async def websocket_detect(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Try to detect wake word(s) from a binary audio stream.

    Audio must be 16Khz sample rate with 16-bit mono PCM samples.
    """
    timestamp_ms = msg.get("timestamp_start", 0)
    entity_id = msg.get("entity_id", async_default_engine(hass))
    engine = async_get_wake_word_detection_entity(hass, entity_id)

    if engine is None:
        raise ValueError("Wake word provider not found")

    handler_id: int | None = None
    unregister_handler: Callable[[], None] | None = None

    # Audio pipeline that will receive audio as binary websocket messages
    audio_queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def wwd_stream() -> AsyncGenerator[tuple[bytes, int], None]:
        nonlocal timestamp_ms

        # Yield until we receive an empty chunk
        while chunk := await audio_queue.get():
            chunk_ms = (len(chunk) / 2) // 16  # 16-bit mono @16KHz
            timestamp_ms += chunk_ms
            yield (chunk, timestamp_ms)

    def handle_binary(
        _hass: HomeAssistant,
        _connection: websocket_api.ActiveConnection,
        data: bytes,
    ) -> None:
        # Forward to WWD audio stream
        audio_queue.put_nowait(data)

    handler_id, unregister_handler = connection.async_register_binary_handler(
        handle_binary
    )

    # Confirm subscription
    connection.send_result(msg["id"], {"handler_id": handler_id})

    run_task = hass.async_create_task(engine.async_process_audio_stream(wwd_stream()))

    # Cancel pipeline if user unsubscribes
    connection.subscriptions[msg["id"]] = run_task.cancel

    try:
        result = await run_task
        connection.send_message({} if result is None else asdict(result))
    finally:
        if unregister_handler is not None:
            # Unregister binary handler
            unregister_handler()
