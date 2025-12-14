"""YoLink Valve."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yolink.client_request import ClientRequest
from yolink.const import (
    ATTR_DEVICE_MODEL_A,
    ATTR_DEVICE_MULTI_WATER_METER_CONTROLLER,
    ATTR_DEVICE_SPRINKLER,
    ATTR_DEVICE_SPRINKLER_V2,
    ATTR_DEVICE_WATER_METER_CONTROLLER,
)
from yolink.device import YoLinkDevice

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityDescription,
    ValveEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEV_MODEL_WATER_METER_YS5007, DOMAIN
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


@dataclass(frozen=True)
class YoLinkValveEntityDescription(ValveEntityDescription):
    """YoLink ValveEntityDescription."""

    exists_fn: Callable[[YoLinkDevice], bool] = lambda _: True
    value: Callable = lambda state: state
    channel_index: int | None = None
    should_update_entity: Callable = lambda state: True
    is_available: Callable[[YoLinkDevice, dict[str, Any]], bool] = (
        lambda device, state: True
    )


def sprinkler_valve_available(device: YoLinkDevice, data: dict[str, Any]) -> bool:
    """Check if sprinkler valve is available."""
    if device.device_type == ATTR_DEVICE_SPRINKLER_V2:
        return True
    if (state := data.get("state")) is not None:
        if (mode := state.get("mode")) is not None:
            return mode == "manual"
    return False


DEVICE_TYPES: tuple[YoLinkValveEntityDescription, ...] = (
    YoLinkValveEntityDescription(
        key="valve_state",
        translation_key="meter_valve_state",
        device_class=ValveDeviceClass.WATER,
        value=lambda value: value != "open" if value is not None else None,
        exists_fn=lambda device: device.device_type
        == ATTR_DEVICE_WATER_METER_CONTROLLER
        and not device.device_model_name.startswith(DEV_MODEL_WATER_METER_YS5007),
    ),
    YoLinkValveEntityDescription(
        key="valve_1_state",
        translation_key="meter_valve_1_state",
        device_class=ValveDeviceClass.WATER,
        value=lambda value: value != "open" if value is not None else None,
        exists_fn=lambda device: (
            device.device_type == ATTR_DEVICE_MULTI_WATER_METER_CONTROLLER
        ),
        channel_index=0,
    ),
    YoLinkValveEntityDescription(
        key="valve_2_state",
        translation_key="meter_valve_2_state",
        device_class=ValveDeviceClass.WATER,
        value=lambda value: value != "open" if value is not None else None,
        exists_fn=lambda device: (
            device.device_type == ATTR_DEVICE_MULTI_WATER_METER_CONTROLLER
        ),
        channel_index=1,
    ),
    YoLinkValveEntityDescription(
        key="valve",
        translation_key="sprinkler_valve",
        device_class=ValveDeviceClass.WATER,
        value=lambda value: value is False if value is not None else None,
        exists_fn=lambda device: (
            device.device_type in [ATTR_DEVICE_SPRINKLER, ATTR_DEVICE_SPRINKLER_V2]
        ),
        should_update_entity=lambda value: value is not None,
        is_available=sprinkler_valve_available,
    ),
)

DEVICE_TYPE = [
    ATTR_DEVICE_WATER_METER_CONTROLLER,
    ATTR_DEVICE_MULTI_WATER_METER_CONTROLLER,
    ATTR_DEVICE_SPRINKLER,
    ATTR_DEVICE_SPRINKLER_V2,
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up YoLink valve from a config entry."""
    device_coordinators = hass.data[DOMAIN][config_entry.entry_id].device_coordinators
    valve_device_coordinators = [
        device_coordinator
        for device_coordinator in device_coordinators.values()
        if device_coordinator.device.device_type in DEVICE_TYPE
    ]
    async_add_entities(
        YoLinkValveEntity(config_entry, valve_device_coordinator, description)
        for valve_device_coordinator in valve_device_coordinators
        for description in DEVICE_TYPES
        if description.exists_fn(valve_device_coordinator.device)
    )


class YoLinkValveEntity(YoLinkEntity, ValveEntity):
    """YoLink Valve Entity."""

    entity_description: YoLinkValveEntityDescription

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
        description: YoLinkValveEntityDescription,
    ) -> None:
        """Init YoLink valve."""
        super().__init__(config_entry, coordinator)
        self._attr_supported_features = (
            ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
        )
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.device.device_id} {self.entity_description.key}"
        )

    @callback
    def update_entity_state(self, state: dict[str, str | list[str]]) -> None:
        """Update HA Entity State."""
        if (
            attr_val := self.entity_description.value(
                state.get(self.entity_description.key)
            )
        ) is None and self.entity_description.should_update_entity(attr_val) is False:
            return
        if self.entity_description.is_available(self.coordinator.device, state) is True:
            self._attr_is_closed = attr_val
            self._attr_available = True
        else:
            self._attr_available = False
        self.async_write_ha_state()

    async def _async_invoke_device(self, state: str) -> None:
        """Call setState api to change valve state."""
        if (
            self.coordinator.device.is_support_mode_switching()
            and self.coordinator.dev_net_type == ATTR_DEVICE_MODEL_A
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="valve_inoperable_currently"
            )
        if (
            self.coordinator.device.device_type
            == ATTR_DEVICE_MULTI_WATER_METER_CONTROLLER
        ):
            channel_index = self.entity_description.channel_index
            if channel_index is not None:
                await self.call_device(
                    ClientRequest("setState", {"valves": {str(channel_index): state}})
                )
        if self.coordinator.device.device_type == ATTR_DEVICE_SPRINKLER:
            await self.call_device(
                ClientRequest(
                    "setManualWater", {"state": "start" if state == "open" else "stop"}
                )
            )
        if self.coordinator.device.device_type == ATTR_DEVICE_SPRINKLER_V2:
            await self.call_device(
                ClientRequest("setState", {"running": state == "open"})
            )
        else:
            await self.call_device(ClientRequest("setState", {"valve": state}))
        self._attr_is_closed = state == "close"
        self.async_write_ha_state()

    async def async_open_valve(self) -> None:
        """Open the valve."""
        await self._async_invoke_device("open")

    async def async_close_valve(self) -> None:
        """Close valve."""
        await self._async_invoke_device("close")

    @property
    def available(self) -> bool:
        """Return true is device is available."""
        return self._attr_available and super().available
