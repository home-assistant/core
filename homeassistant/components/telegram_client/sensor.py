"""Telegram client sensor entity class."""

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_FIRST_NAME,
    CONF_LAST_NAME,
    CONF_LAST_SENT_MESSAGE_ID,
    CONF_PHONE,
    CONF_TYPE,
    CONF_TYPE_CLIENT,
    CONF_USER_ID,
    CONF_USERNAME,
)
from .entity import TelegramClientEntity

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=CONF_USER_ID,
        translation_key=CONF_USER_ID,
        name="User ID",
        icon="mdi:id-card",
    ),
    SensorEntityDescription(
        key=CONF_USERNAME,
        translation_key=CONF_USERNAME,
        name="Username",
        icon="mdi:account",
    ),
    SensorEntityDescription(
        key=CONF_LAST_NAME,
        translation_key=CONF_LAST_NAME,
        name="Last name",
    ),
    SensorEntityDescription(
        key=CONF_FIRST_NAME,
        translation_key=CONF_FIRST_NAME,
        name="First name",
    ),
    SensorEntityDescription(
        key=CONF_PHONE,
        translation_key=CONF_PHONE,
        name="Phone",
        icon="mdi:card-account-phone",
    ),
    SensorEntityDescription(
        key=CONF_LAST_SENT_MESSAGE_ID,
        translation_key=CONF_LAST_SENT_MESSAGE_ID,
        name="Last sent message ID",
        icon="mdi:message-arrow-right",
        entity_category=EntityCategory.DIAGNOSTIC,
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

    entity_description: SensorEntityDescription

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.entity_description.key in self.coordinator.data:
            self._attr_native_value = self.coordinator.data[self.entity_description.key]
        else:
            self._attr_native_value = None

        self.async_write_ha_state()
