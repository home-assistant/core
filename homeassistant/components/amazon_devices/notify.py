"""Support for notification entity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.notify import NotifyEntity, NotifyEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator
from .entity import AmazonEntity


@dataclass(frozen=True, kw_only=True)
class AmazonNotifyEntityDescription(NotifyEntityDescription):
    """Amazon Devices notify entity description."""

    method: str
    subkey: str


NOTIFY: Final = (
    AmazonNotifyEntityDescription(
        key="speak",
        translation_key="speak",
        subkey="AUDIO_PLAYER",
        method="call_alexa_speak",
    ),
    AmazonNotifyEntityDescription(
        key="announce",
        translation_key="announce",
        subkey="AUDIO_PLAYER",
        method="call_alexa_announcement",
    ),
    AmazonNotifyEntityDescription(
        key="sound",
        translation_key="sound",
        subkey="AUDIO_PLAYER",
        method="call_alexa_sound",
    ),
    AmazonNotifyEntityDescription(
        key="custom",
        translation_key="custom",
        subkey="MICROPHONE",
        method="call_alexa_text_command",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Amazon Devices notification entity based on a config entry."""

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

    def __init__(
        self,
        coordinator: AmazonDevicesCoordinator,
        serial_num: str,
        description: AmazonNotifyEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, serial_num)
        self.entity_description = description
        self._attr_unique_id = f"{serial_num}-{description.key}"

    async def async_send_message(
        self, message: str, title: str | None = None, **kwargs: Any
    ) -> None:
        """Send a message."""

        method = getattr(self.coordinator.api, self.entity_description.method)

        if TYPE_CHECKING:
            assert method is not None

        await method(self.device, message)
