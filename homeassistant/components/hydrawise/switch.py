"""Support for Hydrawise cloud switches."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from pydrawise.schema import Zone
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
from homeassistant.util import dt as dt_util

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
        vol.Optional(
            CONF_WATERING_TIME, default=DEFAULT_WATERING_TIME.total_seconds() // 60
        ): vol.All(vol.In(ALLOWED_WATERING_TIME)),
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
    async_add_entities(
        HydrawiseSwitch(coordinator, description, controller, zone)
        for controller in coordinator.data.controllers.values()
        for zone in controller.zones
        for description in SWITCH_TYPES
    )


class HydrawiseSwitch(HydrawiseEntity, SwitchEntity):
    """A switch implementation for Hydrawise device."""

    zone: Zone

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if self.entity_description.key == "manual_watering":
            await self.coordinator.api.start_zone(
                self.zone, custom_run_duration=DEFAULT_WATERING_TIME.total_seconds()
            )
        elif self.entity_description.key == "auto_watering":
            await self.coordinator.api.resume_zone(self.zone)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if self.entity_description.key == "manual_watering":
            await self.coordinator.api.stop_zone(self.zone)
        elif self.entity_description.key == "auto_watering":
            await self.coordinator.api.suspend_zone(
                self.zone, dt_util.now() + timedelta(days=365)
            )
        self._attr_is_on = False
        self.async_write_ha_state()

    def _update_attrs(self) -> None:
        """Update state attributes."""
        if self.entity_description.key == "manual_watering":
            self._attr_is_on = self.zone.scheduled_runs.current_run is not None
        elif self.entity_description.key == "auto_watering":
            self._attr_is_on = self.zone.status.suspended_until is None
