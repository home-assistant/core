"""Telegram client sensor entities."""

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import TelegramClientEntity


@dataclass(frozen=True, kw_only=True)
class TelegramClientBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Telegram client sensor entity."""

    data_key: str


BINARY_SENSORS: tuple[TelegramClientBinarySensorEntityDescription, ...] = (
    TelegramClientBinarySensorEntityDescription(
        key="restricted",
        translation_key="restricted",
        name="Restricted",
        data_key="me",
    ),
    TelegramClientBinarySensorEntityDescription(
        key="premium",
        translation_key="premium",
        name="Premium",
        data_key="me",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Telegram client binary sensor entity."""
    coordinator = entry.runtime_data
    async_add_entities(
        TelegramClientBinarySensorEntity(coordinator, entity_description)
        for entity_description in BINARY_SENSORS
    )


class TelegramClientBinarySensorEntity(TelegramClientEntity, BinarySensorEntity):
    """Telegram client binary_sensor entity class."""

    entity_description: TelegramClientBinarySensorEntityDescription

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            self.entity_description.data_key in self.coordinator.data
            and self.entity_description.key
            in self.coordinator.data[self.entity_description.data_key]
        ):
            self._attr_is_on = self.coordinator.data[self.entity_description.data_key][
                self.entity_description.key
            ]
        else:
            self._attr_is_on = None

        self.async_write_ha_state()
