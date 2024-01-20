"""Binary Sensor platform for JVC Projector integration."""

from __future__ import annotations

from jvcprojector import const

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JvcProjectorDataUpdateCoordinator
from .const import DOMAIN
from .entity import JvcProjectorEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the JVC Projector platform from a config entry."""
    coordinator: JvcProjectorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([JvcBinarySensor(coordinator)])


class JvcBinarySensor(JvcProjectorEntity, BinarySensorEntity):
    """The entity class for JVC Projector integration."""

    _attr_has_entity_name = True
    _attr_name = None

    """_attr_device_class = BinarySensorDeviceClass.POWER"""
    icon = "mdi:power"

    def __init__(
        self,
        coordinator: JvcProjectorDataUpdateCoordinator,
    ) -> None:
        """Initialize the JVC Projector sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_unique_id = f"{self._coordinator.device.mac}_BinarySensor"
        self._attributes: dict[str, str] = {}

    @property
    def is_on(self) -> bool:
        """Return true if the JVC is on."""
        return self.coordinator.data["power"] in [const.ON, const.WARMING]
