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
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ALLOWED_WATERING_TIME,
    CONF_WATERING_TIME,
    DEFAULT_WATERING_TIME,
    DOMAIN,
)
from .coordinator import HydrawiseDataUpdateCoordinator
from .entity import HydrawiseEntity

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="auto_watering",
        translation_key="auto_watering",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key="manual_watering",
        translation_key="manual_watering",
        device_class=SwitchDeviceClass.SWITCH,
    ),
)

SWITCH_KEYS: list[str] = [desc.key for desc in SWITCH_TYPES]

# Deprecated since Home Assistant 2023.10.0
# Can be removed completely in 2024.4.0
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
    return  # pragma: no cover


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hydrawise switch platform."""
    coordinator: HydrawiseDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    default_watering_timer = DEFAULT_WATERING_TIME

    entities = [
        HydrawiseSwitch(
            data=zone,
            coordinator=coordinator,
            description=description,
            default_watering_timer=default_watering_timer,
        )
        for zone in coordinator.api.relays
        for description in SWITCH_TYPES
    ]

    async_add_entities(entities)


class HydrawiseSwitch(HydrawiseEntity, SwitchEntity):
    """A switch implementation for Hydrawise device."""

    def __init__(
        self,
        *,
        data: dict[str, Any],
        coordinator: HydrawiseDataUpdateCoordinator,
        description: SwitchEntityDescription,
        default_watering_timer: int,
    ) -> None:
        """Initialize a switch for Hydrawise device."""
        super().__init__(data=data, coordinator=coordinator, description=description)
        self._default_watering_timer = default_watering_timer

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        zone_number = self.data["relay"]
        if self.entity_description.key == "manual_watering":
            self.coordinator.api.run_zone(self._default_watering_timer, zone_number)
        elif self.entity_description.key == "auto_watering":
            self.coordinator.api.suspend_zone(0, zone_number)
        self._attr_is_on = True
        self.async_write_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        zone_number = self.data["relay"]
        if self.entity_description.key == "manual_watering":
            self.coordinator.api.run_zone(0, zone_number)
        elif self.entity_description.key == "auto_watering":
            self.coordinator.api.suspend_zone(365, zone_number)
        self._attr_is_on = False
        self.async_write_ha_state()

    def _update_attrs(self) -> None:
        """Update state attributes."""
        zone_number = self.data["relay"]
        timestr = self.coordinator.api.relays_by_zone_number[zone_number]["timestr"]
        if self.entity_description.key == "manual_watering":
            self._attr_is_on = timestr == "Now"
        elif self.entity_description.key == "auto_watering":
            self._attr_is_on = timestr not in {"", "Now"}
