"""Support for Rain Bird Irrigation system LNK Wi-Fi Module."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_DURATION, CONF_IMPORTED_NAMES, DOMAIN, MANUFACTURER
from .coordinator import RainbirdUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_START_IRRIGATION = "start_irrigation"

SERVICE_SCHEMA_IRRIGATION = {
    vol.Required(ATTR_DURATION): cv.positive_float,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry for a Rain Bird irrigation switches."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        RainBirdSwitch(
            coordinator,
            zone,
            config_entry.options[ATTR_DURATION],
            config_entry.data.get(CONF_IMPORTED_NAMES, {}).get(str(zone)),
        )
        for zone in coordinator.data.zones
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_START_IRRIGATION,
        SERVICE_SCHEMA_IRRIGATION,
        "async_turn_on",
    )


class RainBirdSwitch(CoordinatorEntity[RainbirdUpdateCoordinator], SwitchEntity):
    """Representation of a Rain Bird switch."""

    def __init__(
        self,
        coordinator: RainbirdUpdateCoordinator,
        zone: int,
        duration_minutes: int,
        imported_name: str | None,
    ) -> None:
        """Initialize a Rain Bird Switch Device."""
        super().__init__(coordinator)
        self._zone = zone
        if imported_name:
            self._attr_name = imported_name
            self._attr_has_entity_name = False
        else:
            self._attr_name = None
            self._attr_has_entity_name = True
        self._state = None
        self._duration_minutes = duration_minutes
        self._attr_unique_id = f"{coordinator.serial_number}-{zone}"
        self._attr_device_info = DeviceInfo(
            name=f"{MANUFACTURER} Sprinkler {zone}",
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer=MANUFACTURER,
            via_device=(DOMAIN, coordinator.serial_number),
        )

    @property
    def extra_state_attributes(self):
        """Return state attributes."""
        return {"zone": self._zone}

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.coordinator.controller.irrigate_zone(
            int(self._zone),
            int(kwargs.get(ATTR_DURATION, self._duration_minutes)),
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.coordinator.controller.stop_irrigation()
        await self.coordinator.async_request_refresh()

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._zone in self.coordinator.data.active_zones
