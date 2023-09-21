"""Binary sensor entities for LIFX integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, HEV_CYCLE_STATE
from .coordinator import LIFXUpdateCoordinator
from .entity import LIFXEntity
from .util import lifx_features

HEV_CYCLE_STATE_SENSOR = BinarySensorEntityDescription(
    key=HEV_CYCLE_STATE,
    translation_key="clean_cycle",
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

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"
        self._async_update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Handle coordinator updates."""
        self._attr_is_on = self.coordinator.async_get_hev_cycle_state()
