"""Support for Hydrawise cloud switches."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pydrawise import Hydrawise, Zone

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DEFAULT_WATERING_TIME, DOMAIN
from .coordinator import HydrawiseDataUpdateCoordinator
from .entity import HydrawiseEntity


@dataclass(frozen=True, kw_only=True)
class HydrawiseSwitchEntityDescription(SwitchEntityDescription):
    """Describes Hydrawise binary sensor."""

    turn_on_fn: Callable[[Hydrawise, Zone], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[Hydrawise, Zone], Coroutine[Any, Any, None]]
    value_fn: Callable[[Zone], bool]


SWITCH_TYPES: tuple[HydrawiseSwitchEntityDescription, ...] = (
    HydrawiseSwitchEntityDescription(
        key="auto_watering",
        translation_key="auto_watering",
        device_class=SwitchDeviceClass.SWITCH,
        value_fn=lambda zone: zone.status.suspended_until is None,
        turn_on_fn=lambda api, zone: api.resume_zone(zone),
        turn_off_fn=lambda api, zone: api.suspend_zone(
            zone, dt_util.now() + timedelta(days=365)
        ),
    ),
    HydrawiseSwitchEntityDescription(
        key="manual_watering",
        translation_key="manual_watering",
        device_class=SwitchDeviceClass.SWITCH,
        value_fn=lambda zone: zone.scheduled_runs.current_run is not None,
        turn_on_fn=lambda api, zone: api.start_zone(
            zone,
            custom_run_duration=int(DEFAULT_WATERING_TIME.total_seconds()),
        ),
        turn_off_fn=lambda api, zone: api.stop_zone(zone),
    ),
)

SWITCH_KEYS: list[str] = [desc.key for desc in SWITCH_TYPES]


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
        HydrawiseSwitch(coordinator, description, controller, zone_id=zone.id)
        for controller in coordinator.data.controllers.values()
        for zone in controller.zones
        for description in SWITCH_TYPES
    )


class HydrawiseSwitch(HydrawiseEntity, SwitchEntity):
    """A switch implementation for Hydrawise device."""

    entity_description: HydrawiseSwitchEntityDescription
    zone: Zone

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self.entity_description.turn_on_fn(self.coordinator.api, self.zone)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.entity_description.turn_off_fn(self.coordinator.api, self.zone)
        self._attr_is_on = False
        self.async_write_ha_state()

    def _update_attrs(self) -> None:
        """Update state attributes."""
        self._attr_is_on = self.entity_description.value_fn(self.zone)
