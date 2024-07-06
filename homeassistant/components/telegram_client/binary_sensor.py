"""Telegram client sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass

from telethon import TelegramClient

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device import TelegramClientDevice
from .entity import TelegramClientEntity


@dataclass(frozen=True, kw_only=True)
class TelegramClientBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Telegram client sensor entity."""

    value_fn: Callable[[TelegramClient], str | int]
    data_key: str


BINARY_SENSORS: tuple[TelegramClientBinarySensorEntityDescription, ...] = (
    TelegramClientBinarySensorEntityDescription(
        key="restricted",
        translation_key="restricted",
        name="Restricted",
        value_fn=lambda data: data.restricted,
        data_key="me",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Telegram client binary sensor entity."""
    device = hass.data[DOMAIN].get(entry.entry_id)
    async_add_entities(
        TelegramClientBinarySensorEntity(device, entity_description)
        for entity_description in BINARY_SENSORS
    )


class TelegramClientBinarySensorEntity(TelegramClientEntity, BinarySensorEntity):
    """Telegram client binary_sensor entity class."""

    _attr_should_poll = False

    def __init__(
        self,
        device: TelegramClientDevice,
        entity_description: TelegramClientBinarySensorEntityDescription,
    ) -> None:
        """Init."""
        super().__init__(device, entity_description)
        self._entity_description = entity_description
        device.binary_sensors.append(self)

    def update_state(self):
        """Update the state of the sensor based on new data."""
        self._attr_is_on = self._entity_description.value_fn(
            self.device.data[self._entity_description.data_key]
        )
        self.async_schedule_update_ha_state()
