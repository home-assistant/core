"""Support for Hydrawise cloud switches."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA,
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ALLOWED_WATERING_TIME,
    CONF_WATERING_TIME,
    DEFAULT_WATERING_TIME,
    DOMAIN,
    LOGGER,
)
from .coordinator import HydrawiseDataUpdateCoordinator
from .entity import HydrawiseEntity

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="auto_watering",
        name="Automatic Watering",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key="manual_watering",
        name="Manual Watering",
        device_class=SwitchDeviceClass.SWITCH,
    ),
)

SWITCH_KEYS: list[str] = [desc.key for desc in SWITCH_TYPES]

# Deprecated since Home Assistant 2023.9.0
# Can be removed completely in 2024.3.0
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SWITCH_KEYS): vol.All(
            cv.ensure_list, [vol.In(SWITCH_KEYS)]
        ),
        vol.Optional(CONF_WATERING_TIME, default=DEFAULT_WATERING_TIME): vol.All(
            vol.In(ALLOWED_WATERING_TIME)
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a sensor for a Hydrawise device."""
    # We don't need to trigger import flow from here as it's triggered from `__init__.py`
    return


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hydrawise switch platform."""
    coordinator: HydrawiseDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities = [
        HydrawiseSwitch(
            data=zone,
            coordinator=coordinator,
            description=description,
        )
        for zone in coordinator.api.relays
        for description in SWITCH_TYPES
    ]

    async_add_entities(entities)


class HydrawiseSwitch(HydrawiseEntity, SwitchEntity):
    """A switch implementation for Hydrawise device."""

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        zone_number = self.data["relay"]
        if self.entity_description.key == "manual_watering":
            self.coordinator.api.run_zone(DEFAULT_WATERING_TIME, zone_number)
        elif self.entity_description.key == "auto_watering":
            self.coordinator.api.suspend_zone(0, zone_number)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        zone_number = self.data["relay"]
        if self.entity_description.key == "manual_watering":
            self.coordinator.api.run_zone(0, zone_number)
        elif self.entity_description.key == "auto_watering":
            self.coordinator.api.suspend_zone(365, zone_number)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update device state."""
        zone_number = self.data["relay"]
        LOGGER.debug("Updating Hydrawise switch: %s", self.name)
        timestr = self.coordinator.api.relays_by_zone_number[zone_number]["timestr"]
        if self.entity_description.key == "manual_watering":
            self._attr_is_on = timestr == "Now"
        elif self.entity_description.key == "auto_watering":
            self._attr_is_on = timestr not in {"", "Now"}
        super()._handle_coordinator_update()
