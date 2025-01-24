"""Support for Rain Bird Irrigation system LNK Wi-Fi Module."""

from __future__ import annotations

import logging

from pyrainbird.exceptions import RainbirdApiException, RainbirdDeviceBusyException
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import VolDictType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_DURATION, CONF_IMPORTED_NAMES, DOMAIN, MANUFACTURER
from .coordinator import RainbirdUpdateCoordinator
from .types import RainbirdConfigEntry

_LOGGER = logging.getLogger(__name__)

SERVICE_START_IRRIGATION = "start_irrigation"

SERVICE_SCHEMA_IRRIGATION: VolDictType = {
    vol.Required(ATTR_DURATION): cv.positive_float,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RainbirdConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry for a Rain Bird irrigation switches."""
    coordinator = config_entry.runtime_data.coordinator
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
        _LOGGER.debug("coordinator.unique_id=%s", coordinator.unique_id)
        if coordinator.unique_id is not None:
            self._attr_unique_id = f"{coordinator.unique_id}-{zone}"
        device_name = f"{MANUFACTURER} Sprinkler {zone}"
        if imported_name:
            self._attr_name = imported_name
            self._attr_has_entity_name = False
        else:
            self._attr_name = None if coordinator.unique_id is not None else device_name
            self._attr_has_entity_name = True
        self._duration_minutes = duration_minutes
        if coordinator.unique_id is not None and self._attr_unique_id is not None:
            self._attr_device_info = DeviceInfo(
                name=device_name,
                identifiers={(DOMAIN, self._attr_unique_id)},
                manufacturer=MANUFACTURER,
                via_device=(DOMAIN, coordinator.unique_id),
            )

    @property
    def extra_state_attributes(self):
        """Return state attributes."""
        return {"zone": self._zone}

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        try:
            await self.coordinator.controller.irrigate_zone(
                int(self._zone),
                int(kwargs.get(ATTR_DURATION, self._duration_minutes)),
            )
        except RainbirdDeviceBusyException as err:
            raise HomeAssistantError(
                "Rain Bird device is busy; Wait and try again"
            ) from err
        except RainbirdApiException as err:
            raise HomeAssistantError("Rain Bird device failure") from err

        # The device reflects the old state for a few moments. Update the
        # state manually and trigger a refresh after a short debounced delay.
        self.coordinator.data.active_zones.add(self._zone)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        try:
            await self.coordinator.controller.stop_irrigation()
        except RainbirdDeviceBusyException as err:
            raise HomeAssistantError(
                "Rain Bird device is busy; Wait and try again"
            ) from err
        except RainbirdApiException as err:
            raise HomeAssistantError("Rain Bird device failure") from err

        # The device reflects the old state for a few moments. Update the
        # state manually and trigger a refresh after a short debounced delay.
        if self.is_on:
            self.coordinator.data.active_zones.remove(self._zone)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._zone in self.coordinator.data.active_zones
