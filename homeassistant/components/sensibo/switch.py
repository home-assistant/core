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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity, api_call_decorator

PARALLEL_UPDATES = 0


@dataclass
class DeviceBaseEntityDescriptionMixin:
    """Mixin for required Sensibo Device description keys."""

    value_fn: Callable[[SensiboDevice], bool | None]
    extra_fn: Callable[[SensiboDevice], dict[str, str | bool | None]] | None
    command_on: str
    command_off: str
    data_key: str


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
        data_key="timer_on",
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
        data_key="pure_boost_enabled",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo Switch platform."""

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
        if self.entity_description.key == "timer_on_switch":
            await self.turn_on_timer(
                device_data=self.device_data,
                key=self.entity_description.data_key,
                value=True,
            )
        if self.entity_description.key == "pure_boost_switch":
            await self.turn_on_off_pure_boost(
                device_data=self.device_data,
                key=self.entity_description.data_key,
                value=True,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        if self.entity_description.key == "timer_on_switch":
            await self.turn_off_timer(
                device_data=self.device_data,
                key=self.entity_description.data_key,
                value=True,
            )
        if self.entity_description.key == "pure_boost_switch":
            await self.turn_on_off_pure_boost(
                device_data=self.device_data,
                key=self.entity_description.data_key,
                value=True,
            )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional attributes."""
        if self.entity_description.extra_fn:
            return self.entity_description.extra_fn(self.device_data)
        return None

    @api_call_decorator
    async def turn_on_timer(
        self, device_data: SensiboDevice, key: Any, value: Any
    ) -> bool:
        """Make service call to api for setting timer."""
        result = {}
        new_state = bool(device_data.ac_states["on"] is False)
        data = {
            "minutesFromNow": 60,
            "acState": {**device_data.ac_states, "on": new_state},
        }
        result = await self._client.async_set_timer(self._device_id, data)
        return bool(result.get("status") == "success")

    @api_call_decorator
    async def turn_off_timer(
        self, device_data: SensiboDevice, key: Any, value: Any
    ) -> bool:
        """Make service call to api for deleting timer."""
        result = {}
        result = await self._client.async_del_timer(self._device_id)
        return bool(result.get("status") == "success")

    @api_call_decorator
    async def turn_on_off_pure_boost(
        self, device_data: SensiboDevice, key: Any, value: Any
    ) -> bool:
        """Make service call to api for setting Pure Boost."""
        result = {}
        new_state = bool(device_data.pure_boost_enabled is False)
        data: dict[str, Any] = {"enabled": new_state}
        if device_data.pure_measure_integration is None:
            data["sensitivity"] = "N"
            data["measurementsIntegration"] = True
            data["acIntegration"] = False
            data["geoIntegration"] = False
            data["primeIntegration"] = False
        result = await self._client.async_set_pureboost(self._device_id, data)
        return bool(result.get("status") == "success")
