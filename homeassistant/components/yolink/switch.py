"""YoLink Switch."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yolink.client_request import ClientRequest
from yolink.const import (
    ATTR_DEVICE_MANIPULATOR,
    ATTR_DEVICE_MULTI_OUTLET,
    ATTR_DEVICE_OUTLET,
    ATTR_DEVICE_SWITCH,
)
from yolink.device import YoLinkDevice
from yolink.outlet_request_builder import OutletRequestBuilder

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


@dataclass(frozen=True)
class YoLinkSwitchEntityDescription(SwitchEntityDescription):
    """YoLink SwitchEntityDescription."""

    exists_fn: Callable[[YoLinkDevice], bool] = lambda _: True
    plug_index: int | None = None


DEVICE_TYPES: tuple[YoLinkSwitchEntityDescription, ...] = (
    YoLinkSwitchEntityDescription(
        key="outlet_state",
        device_class=SwitchDeviceClass.OUTLET,
        name=None,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_OUTLET,
    ),
    YoLinkSwitchEntityDescription(
        key="manipulator_state",
        name=None,
        icon="mdi:pipe",
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_MANIPULATOR,
    ),
    YoLinkSwitchEntityDescription(
        key="switch_state",
        name=None,
        device_class=SwitchDeviceClass.SWITCH,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_SWITCH,
    ),
    YoLinkSwitchEntityDescription(
        key="multi_outlet_usb_ports",
        translation_key="usb_ports",
        device_class=SwitchDeviceClass.OUTLET,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_MULTI_OUTLET,
        plug_index=0,
    ),
    YoLinkSwitchEntityDescription(
        key="multi_outlet_plug_1",
        translation_key="plug_1",
        device_class=SwitchDeviceClass.OUTLET,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_MULTI_OUTLET,
        plug_index=1,
    ),
    YoLinkSwitchEntityDescription(
        key="multi_outlet_plug_2",
        translation_key="plug_2",
        device_class=SwitchDeviceClass.OUTLET,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_MULTI_OUTLET,
        plug_index=2,
    ),
    YoLinkSwitchEntityDescription(
        key="multi_outlet_plug_3",
        translation_key="plug_3",
        device_class=SwitchDeviceClass.OUTLET,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_MULTI_OUTLET,
        plug_index=3,
    ),
    YoLinkSwitchEntityDescription(
        key="multi_outlet_plug_4",
        translation_key="plug_4",
        device_class=SwitchDeviceClass.OUTLET,
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_MULTI_OUTLET,
        plug_index=4,
    ),
)

DEVICE_TYPE = [
    ATTR_DEVICE_MANIPULATOR,
    ATTR_DEVICE_MULTI_OUTLET,
    ATTR_DEVICE_OUTLET,
    ATTR_DEVICE_SWITCH,
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoLink switch from a config entry."""
    device_coordinators = hass.data[DOMAIN][config_entry.entry_id].device_coordinators
    switch_device_coordinators = [
        device_coordinator
        for device_coordinator in device_coordinators.values()
        if device_coordinator.device.device_type in DEVICE_TYPE
    ]
    entities = []
    for switch_device_coordinator in switch_device_coordinators:
        for description in DEVICE_TYPES:
            if description.exists_fn(switch_device_coordinator.device):
                entities.append(
                    YoLinkSwitchEntity(
                        config_entry, switch_device_coordinator, description
                    )
                )
    async_add_entities(entities)


class YoLinkSwitchEntity(YoLinkEntity, SwitchEntity):
    """YoLink Switch Entity."""

    entity_description: YoLinkSwitchEntityDescription

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
        description: YoLinkSwitchEntityDescription,
    ) -> None:
        """Init YoLink switch."""
        super().__init__(config_entry, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.device.device_id} {self.entity_description.key}"
        )

    def _get_state(
        self, state_value: str | list[str] | None, plug_index: int | None
    ) -> bool | None:
        """Parse state value."""
        if isinstance(state_value, list) and plug_index is not None:
            return state_value[plug_index] == "open"
        return state_value == "open" if state_value is not None else None

    @callback
    def update_entity_state(self, state: dict[str, str | list[str]]) -> None:
        """Update HA Entity State."""
        self._attr_is_on = self._get_state(
            state.get("state"), self.entity_description.plug_index
        )
        self.async_write_ha_state()

    async def call_state_change(self, state: str) -> None:
        """Call setState api to change switch state."""
        client_request: ClientRequest = None
        if self.coordinator.device.device_type in [
            ATTR_DEVICE_OUTLET,
            ATTR_DEVICE_MULTI_OUTLET,
        ]:
            client_request = OutletRequestBuilder.set_state_request(
                state, self.entity_description.plug_index
            )
        else:
            client_request = ClientRequest("setState", {"state": state})
        await self.call_device(client_request)
        self._attr_is_on = self._get_state(state, self.entity_description.plug_index)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.call_state_change("open")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.call_state_change("close")
