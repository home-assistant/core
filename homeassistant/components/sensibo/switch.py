"""Switch platform for Sensibo integration."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pysensibo.model import SensiboDevice

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity

PARALLEL_UPDATES = 0


@dataclass
class DeviceBaseEntityDescriptionMixin:
    """Mixin for required Sensibo base description keys."""

    value_fn: Callable[[SensiboDevice], bool | None]
    extra_fn: Callable[[SensiboDevice], dict[str, str | bool | None]] | None
    command_on: str
    command_off: str
    remote_key: str


@dataclass
class SensiboDeviceSwitchEntityDescription(
    SwitchEntityDescription, DeviceBaseEntityDescriptionMixin
):
    """Describes Sensibo Switch entity."""


DEVICE_SWITCH_TYPES: tuple[SensiboDeviceSwitchEntityDescription, ...] = (
    SensiboDeviceSwitchEntityDescription(
        key="timer_on_switch",
        device_class=SwitchDeviceClass.SWITCH,
        name="Timer",
        icon="mdi:timer",
        value_fn=lambda data: data.timer_on,
        extra_fn=lambda data: {"id": data.timer_id, "turn_on": data.timer_state_on},
        command_on="set_timer",
        command_off="del_timer",
        remote_key="timer_on",
    ),
)

PURE_SWITCH_TYPES: tuple[SensiboDeviceSwitchEntityDescription, ...] = (
    SensiboDeviceSwitchEntityDescription(
        key="pure_boost_switch",
        device_class=SwitchDeviceClass.SWITCH,
        name="Pure Boost",
        value_fn=lambda data: data.pure_boost_enabled,
        extra_fn=None,
        command_on="set_pure_boost",
        command_off="set_pure_boost",
        remote_key="pure_boost_enabled",
    ),
)


def build_params(command: str, device_data: SensiboDevice) -> dict[str, Any] | None:
    """Build params for turning on switch."""
    if command == "set_timer":
        new_state = bool(device_data.ac_states["on"] is False)
        params = {
            "minutesFromNow": 60,
            "acState": {**device_data.ac_states, "on": new_state},
        }
        return params
    if command == "set_pure_boost":
        new_state = bool(device_data.pure_boost_enabled is False)
        params = {"enabled": new_state}
        if device_data.pure_measure_integration is None:
            params["sensitivity"] = "N"
            params["measurementsIntegration"] = True
            params["acIntegration"] = False
            params["geoIntegration"] = False
            params["primeIntegration"] = False
        return params
    return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo binary sensor platform."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensiboDeviceSwitch] = []

    entities.extend(
        SensiboDeviceSwitch(coordinator, device_id, description)
        for description in DEVICE_SWITCH_TYPES
        for device_id, device_data in coordinator.data.parsed.items()
        if device_data.model != "pure"
    )
    entities.extend(
        SensiboDeviceSwitch(coordinator, device_id, description)
        for description in PURE_SWITCH_TYPES
        for device_id, device_data in coordinator.data.parsed.items()
        if device_data.model == "pure"
    )

    async_add_entities(entities)


class SensiboDeviceSwitch(SensiboDeviceBaseEntity, SwitchEntity):
    """Representation of a Sensibo Device Switch."""

    entity_description: SensiboDeviceSwitchEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        entity_description: SensiboDeviceSwitchEntityDescription,
    ) -> None:
        """Initiate Sensibo Device Switch."""
        super().__init__(
            coordinator,
            device_id,
        )
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}-{entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self.entity_description.value_fn(self.device_data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        params = build_params(self.entity_description.command_on, self.device_data)
        result = await self.async_send_command(
            self.entity_description.command_on, params
        )

        if result["status"] == "success":
            setattr(self.device_data, self.entity_description.remote_key, True)
            self.async_write_ha_state()
            return await self.coordinator.async_request_refresh()
        raise HomeAssistantError(
            f"Could not execute {self.entity_description.command_on} for device {self.name}"
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        params = build_params(self.entity_description.command_on, self.device_data)
        result = await self.async_send_command(
            self.entity_description.command_off, params
        )

        if result["status"] == "success":
            setattr(self.device_data, self.entity_description.remote_key, False)
            self.async_write_ha_state()
            return await self.coordinator.async_request_refresh()
        raise HomeAssistantError(
            f"Could not execute {self.entity_description.command_off} for device {self.name}"
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional attributes."""
        if self.entity_description.extra_fn:
            return self.entity_description.extra_fn(self.device_data)
        return None
