"""YoLink Valve."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from yolink.client_request import ClientRequest
from yolink.const import ATTR_DEVICE_WATER_METER_CONTROLLER
from yolink.device import YoLinkDevice

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityDescription,
    ValveEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEV_MODEL_WATER_METER_YS5007, DOMAIN
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


@dataclass(frozen=True)
class YoLinkValveEntityDescription(ValveEntityDescription):
    """YoLink ValveEntityDescription."""

    exists_fn: Callable[[YoLinkDevice], bool] = lambda _: True
    value: Callable = lambda state: state


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
)

DEVICE_TYPE = [ATTR_DEVICE_WATER_METER_CONTROLLER]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
        ) is None:
            return
        self._attr_is_closed = attr_val
        self.async_write_ha_state()

    async def _async_invoke_device(self, state: str) -> None:
        """Call setState api to change valve state."""
        await self.call_device(ClientRequest("setState", {"valve": state}))
        self._attr_is_closed = state == "close"
        self.async_write_ha_state()

    async def async_open_valve(self) -> None:
        """Open the valve."""
        await self._async_invoke_device("open")

    async def async_close_valve(self) -> None:
        """Close valve."""
        await self._async_invoke_device("close")
