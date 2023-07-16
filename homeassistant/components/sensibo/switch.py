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
from .entity import SensiboDeviceBaseEntity, async_handle_api_call

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
        translation_key="timer_on_switch",
        device_class=SwitchDeviceClass.SWITCH,
        icon="mdi:timer",
        value_fn=lambda data: data.timer_on,
        extra_fn=lambda data: {"id": data.timer_id, "turn_on": data.timer_state_on},
        command_on="async_turn_on_timer",
        command_off="async_turn_off_timer",
        data_key="timer_on",
    ),
    SensiboDeviceSwitchEntityDescription(
        key="climate_react_switch",
        translation_key="climate_react_switch",
        device_class=SwitchDeviceClass.SWITCH,
        icon="mdi:wizard-hat",
        value_fn=lambda data: data.smart_on,
        extra_fn=lambda data: {"type": data.smart_type},
        command_on="async_turn_on_off_smart",
        command_off="async_turn_on_off_smart",
        data_key="smart_on",
    ),
)

PURE_SWITCH_TYPES: tuple[SensiboDeviceSwitchEntityDescription, ...] = (
    SensiboDeviceSwitchEntityDescription(
        key="pure_boost_switch",
        translation_key="pure_boost_switch",
        device_class=SwitchDeviceClass.SWITCH,
        value_fn=lambda data: data.pure_boost_enabled,
        extra_fn=None,
        command_on="async_turn_on_off_pure_boost",
        command_off="async_turn_on_off_pure_boost",
        data_key="pure_boost_enabled",
    ),
)

DESCRIPTION_BY_MODELS = {"pure": PURE_SWITCH_TYPES}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo Switch platform."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SensiboDeviceSwitch(coordinator, device_id, description)
        for device_id, device_data in coordinator.data.parsed.items()
        for description in DESCRIPTION_BY_MODELS.get(
            device_data.model, DEVICE_SWITCH_TYPES
        )
    )


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
        func = getattr(SensiboDeviceSwitch, self.entity_description.command_on)
        await func(
            self,
            key=self.entity_description.data_key,
            value=True,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        func = getattr(SensiboDeviceSwitch, self.entity_description.command_off)
        await func(
            self,
            key=self.entity_description.data_key,
            value=False,
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional attributes."""
        if self.entity_description.extra_fn:
            return self.entity_description.extra_fn(self.device_data)
        return None

    @async_handle_api_call
    async def async_turn_on_timer(self, key: str, value: bool) -> bool:
        """Make service call to api for setting timer."""
        data = {
            "minutesFromNow": 60,
            "acState": {**self.device_data.ac_states, "on": value},
        }
        result = await self._client.async_set_timer(self._device_id, data)
        return bool(result.get("status") == "success")

    @async_handle_api_call
    async def async_turn_off_timer(self, key: str, value: bool) -> bool:
        """Make service call to api for deleting timer."""
        result = await self._client.async_del_timer(self._device_id)
        return bool(result.get("status") == "success")

    @async_handle_api_call
    async def async_turn_on_off_pure_boost(self, key: str, value: bool) -> bool:
        """Make service call to api for setting Pure Boost."""
        data: dict[str, Any] = {"enabled": value}
        if self.device_data.pure_measure_integration is None:
            data["sensitivity"] = "N"
            data["measurementsIntegration"] = True
            data["acIntegration"] = False
            data["geoIntegration"] = False
            data["primeIntegration"] = False
        result = await self._client.async_set_pureboost(self._device_id, data)
        return bool(result.get("status") == "success")

    @async_handle_api_call
    async def async_turn_on_off_smart(self, key: str, value: bool) -> bool:
        """Make service call to api for setting Climate React."""
        if self.device_data.smart_type is None:
            raise HomeAssistantError(
                "Use Sensibo Enable Climate React Service once to enable switch or the"
                " Sensibo app"
            )
        data: dict[str, Any] = {"enabled": value}
        result = await self._client.async_enable_climate_react(self._device_id, data)
        return bool(result.get("status") == "success")
