"""Setup Mullvad VPN Binary Sensors."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

BINARY_SENSORS = (
    BinarySensorEntityDescription(
        key="mullvad_exit_ip",
        translation_key="exit_ip",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator = hass.data[DOMAIN]

    async_add_entities(
        MullvadBinarySensor(coordinator, entity_description, config_entry)
        for entity_description in BINARY_SENSORS
    )


class MullvadBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Represents a Mullvad binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: BinarySensorEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the Mullvad binary sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{config_entry.entry_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="Mullvad VPN",
            manufacturer="Mullvad",
        )

    @property
    def is_on(self) -> bool:
        """Return the state for this binary sensor."""
        return self.coordinator.data[self.entity_description.key]
