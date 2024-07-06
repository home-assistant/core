"""Telegram client sensor entity class."""

from collections.abc import Callable
from dataclasses import dataclass

from telethon import TelegramClient

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device import TelegramClientDevice
from .entity import TelegramClientEntity


@dataclass(frozen=True, kw_only=True)
class TelegramClientSensorEntityDescription(SensorEntityDescription):
    """Describes Telegram client sensor entity."""

    value_fn: Callable[[TelegramClient], str | int]
    data_key: str


SENSORS: tuple[TelegramClientSensorEntityDescription, ...] = (
    TelegramClientSensorEntityDescription(
        key="user_id",
        translation_key="user_id",
        name="User ID",
        value_fn=lambda data: data.id,
        data_key="me",
    ),
    TelegramClientSensorEntityDescription(
        key="username",
        translation_key="username",
        name="Username",
        value_fn=lambda data: data.username,
        data_key="me",
    ),
    TelegramClientSensorEntityDescription(
        key="last_name",
        translation_key="last_name",
        name="Last name",
        value_fn=lambda data: data.last_name,
        data_key="me",
    ),
    TelegramClientSensorEntityDescription(
        key="first_name",
        translation_key="first_name",
        name="First name",
        value_fn=lambda data: data.first_name,
        data_key="me",
    ),
    TelegramClientSensorEntityDescription(
        key="phone",
        translation_key="phone",
        name="Phone",
        value_fn=lambda data: data.phone,
        data_key="me",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Telegram client sensor entity."""
    device = hass.data[DOMAIN].get(entry.entry_id)
    async_add_entities(
        TelegramClientSensorEntity(device, entity_description)
        for entity_description in SENSORS
    )


class TelegramClientSensorEntity(TelegramClientEntity, SensorEntity):
    """Telegram client sensor entity class."""

    _attr_should_poll = False

    def __init__(
        self,
        device: TelegramClientDevice,
        entity_description: TelegramClientSensorEntityDescription,
    ) -> None:
        """Init."""
        super().__init__(device, entity_description)
        self._entity_description = entity_description
        device.sensors.append(self)

    def update_state(self):
        """Update the state of the sensor based on new data."""
        self._attr_native_value = self._entity_description.value_fn(
            self.device.data[self._entity_description.data_key]
        )
        self.async_schedule_update_ha_state()
