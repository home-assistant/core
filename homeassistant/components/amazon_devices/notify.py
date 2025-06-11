"""Support for notification entity."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final

from aioamazondevices.api import AmazonDevice, AmazonEchoApi

from homeassistant.components.notify import NotifyEntity, NotifyEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AmazonConfigEntry
from .entity import AmazonEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class AmazonNotifyEntityDescription(NotifyEntityDescription):
    """Alexa Devices notify entity description."""

    method: Callable[[AmazonEchoApi, AmazonDevice, str], Awaitable[None]]
    subkey: str


NOTIFY: Final = (
    AmazonNotifyEntityDescription(
        key="speak",
        translation_key="speak",
        subkey="AUDIO_PLAYER",
        method=lambda api, device, message: api.call_alexa_speak(device, message),
    ),
    AmazonNotifyEntityDescription(
        key="announce",
        translation_key="announce",
        subkey="AUDIO_PLAYER",
        method=lambda api, device, message: api.call_alexa_announcement(
            device, message
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Alexa Devices notification entity based on a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        AmazonNotifyEntity(coordinator, serial_num, sensor_desc)
        for sensor_desc in NOTIFY
        for serial_num in coordinator.data
        if sensor_desc.subkey in coordinator.data[serial_num].capabilities
    )


class AmazonNotifyEntity(AmazonEntity, NotifyEntity):
    """Binary sensor notify platform."""

    entity_description: AmazonNotifyEntityDescription

    async def async_send_message(
        self, message: str, title: str | None = None, **kwargs: Any
    ) -> None:
        """Send a message."""

        await self.entity_description.method(self.coordinator.api, self.device, message)
