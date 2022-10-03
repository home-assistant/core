"""BleBox sensor entities."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BleBoxEntity, create_blebox_entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a BleBox entry."""

    create_blebox_entities(
        hass,
        config_entry,
        async_add_entities,
        BleBoxBinarySensorEntity,
        "binary_sensors",
    )


class BleBoxBinarySensorEntity(BleBoxEntity, BinarySensorEntity):
    """Representation of a BleBox sensor feature."""

    @property
    def is_on(self):
        """Return the state."""
        return self._feature.state

    @property
    def device_class(self):
        """Return the device class."""
        return self._feature.device_class
