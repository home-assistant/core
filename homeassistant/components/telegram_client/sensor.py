"""Telegram client sensor entity class."""

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import TelegramClientEntity


@dataclass(frozen=True, kw_only=True)
class TelegramClientSensorEntityDescription(SensorEntityDescription):
    """Describes Telegram client sensor entity."""

    data_key: str


SENSORS: tuple[TelegramClientSensorEntityDescription, ...] = (
    TelegramClientSensorEntityDescription(
        key="user_id",
        translation_key="user_id",
        name="User ID",
        data_key="me",
    ),
    TelegramClientSensorEntityDescription(
        key="username",
        translation_key="username",
        name="Username",
        data_key="me",
    ),
    TelegramClientSensorEntityDescription(
        key="last_name",
        translation_key="last_name",
        name="Last name",
        data_key="me",
    ),
    TelegramClientSensorEntityDescription(
        key="first_name",
        translation_key="first_name",
        name="First name",
        data_key="me",
    ),
    TelegramClientSensorEntityDescription(
        key="phone",
        translation_key="phone",
        name="Phone",
        data_key="me",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Telegram client sensor entity."""
    coordinator = entry.runtime_data
    async_add_entities(
        TelegramClientSensorEntity(coordinator, entity_description)
        for entity_description in SENSORS
    )


class TelegramClientSensorEntity(TelegramClientEntity, SensorEntity):
    """Telegram client sensor entity class."""

    entity_description: TelegramClientSensorEntityDescription

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.data[
            self.entity_description.data_key
        ][self.entity_description.key]
        self.async_write_ha_state()
