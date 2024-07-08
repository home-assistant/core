"""Telegram client sensor entity class."""

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_FIRST_NAME,
    CONF_LAST_NAME,
    CONF_PHONE,
    CONF_TYPE,
    CONF_TYPE_CLIENT,
    CONF_USER_ID,
    CONF_USERNAME,
)
from .entity import TelegramClientEntity


@dataclass(frozen=True, kw_only=True)
class TelegramClientSensorEntityDescription(SensorEntityDescription):
    """Describes Telegram client sensor entity."""

    data_key: str


SENSORS: tuple[TelegramClientSensorEntityDescription, ...] = (
    TelegramClientSensorEntityDescription(
        key=CONF_USER_ID,
        translation_key=CONF_USER_ID,
        name="User ID",
        data_key="me",
        icon="mdi:id-card",
    ),
    TelegramClientSensorEntityDescription(
        key=CONF_USERNAME,
        translation_key=CONF_USERNAME,
        name="Username",
        data_key="me",
        icon="mdi:account",
    ),
    TelegramClientSensorEntityDescription(
        key=CONF_LAST_NAME,
        translation_key=CONF_LAST_NAME,
        name="Last name",
        data_key="me",
    ),
    TelegramClientSensorEntityDescription(
        key=CONF_FIRST_NAME,
        translation_key=CONF_FIRST_NAME,
        name="First name",
        data_key="me",
    ),
    TelegramClientSensorEntityDescription(
        key=CONF_PHONE,
        translation_key=CONF_PHONE,
        name="Phone",
        data_key="me",
        icon="mdi:card-account-phone",
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
        if entry.data[CONF_TYPE] == CONF_TYPE_CLIENT
        or entity_description.key not in [CONF_PHONE, CONF_LAST_NAME]
    )


class TelegramClientSensorEntity(TelegramClientEntity, SensorEntity):
    """Telegram client sensor entity class."""

    entity_description: TelegramClientSensorEntityDescription

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            self.entity_description.data_key in self.coordinator.data
            and self.entity_description.key
            in self.coordinator.data[self.entity_description.data_key]
        ):
            self._attr_native_value = self.coordinator.data[
                self.entity_description.data_key
            ][self.entity_description.key]
        else:
            self._attr_native_value = None

        self.async_write_ha_state()
