"""Binary sensor entities for LIFX integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, HEV_CYCLE_STATE
from .coordinator import LIFXUpdateCoordinator
from .entity import LIFXEntity
from .util import lifx_features

HEV_CYCLE_STATE_SENSOR = BinarySensorEntityDescription(
    key=HEV_CYCLE_STATE,
    name="Clean Cycle",
    entity_category=EntityCategory.DIAGNOSTIC,
    device_class=BinarySensorDeviceClass.RUNNING,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LIFX from a config entry."""
    coordinator: LIFXUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if lifx_features(coordinator.device)["hev"]:
        async_add_entities(
            [LIFXHevCycleBinarySensorEntity(coordinator, HEV_CYCLE_STATE_SENSOR)]
        )


class LIFXHevCycleBinarySensorEntity(LIFXEntity, BinarySensorEntity):
    """LIFX HEV cycle state binary sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Returns true if a HEV cycle is currently running."""
        return self.coordinator.async_get_hev_cycle_state()
