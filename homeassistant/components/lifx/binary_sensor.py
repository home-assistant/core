"""Binary sensor entities for LIFX integration."""

from typing import override

from lifx import HevLightState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import HEV_CYCLE_STATE
from .coordinator import LIFXConfigEntry, LIFXUpdateCoordinator
from .entity import LIFXEntity

PARALLEL_UPDATES = 0

HEV_CYCLE_STATE_SENSOR = BinarySensorEntityDescription(
    key=HEV_CYCLE_STATE,
    translation_key="clean_cycle",
    entity_category=EntityCategory.DIAGNOSTIC,
    device_class=BinarySensorDeviceClass.RUNNING,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LIFXConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LIFX from a config entry."""
    coordinator = entry.runtime_data

    if coordinator.data.capabilities.has_hev:
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
        super().__init__(coordinator, description)
        self._async_update_attrs()

    @callback
    @override
    def _async_update_attrs(self) -> None:
        """Handle coordinator updates."""
        state = self.coordinator.data
        self._attr_is_on = (
            state.hev_cycle.remaining_s > 0
            if isinstance(state, HevLightState)
            else None
        )
