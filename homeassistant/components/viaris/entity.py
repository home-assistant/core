"""MQTT component mixins and helpers."""
from homeassistant import config_entries
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.util import slugify

from . import ViarisEntityDescription
from .const import CONF_SERIAL_NUMBER, CONF_TOPIC_PREFIX, DOMAIN


class ViarisEntity(Entity):
    """Common viaris entity."""

    def __init__(
        self,
        config_entry: config_entries.ConfigEntry,
        description: ViarisEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        topic_prefix = config_entry.data[CONF_TOPIC_PREFIX]
        serial_number = config_entry.data[CONF_SERIAL_NUMBER]

        self._topic = f"{topic_prefix}/{serial_number}/{description.key}"

        slug = slugify(self._topic.replace("/", "_"))
        self.entity_id = f"{description.domain}.{slug}"

        self._attr_unique_id = "-".join(
            [serial_number, description.domain, description.key, description.attribute]
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=config_entry.title,
        )
