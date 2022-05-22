"""YoLink Switch."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yolink.device import YoLinkDevice
from yolink.exception import YoLinkAuthFailError, YoLinkClientError

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_COORDINATOR, ATTR_DEVICE_OUTLET, DOMAIN
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


@dataclass
class YoLinkSwitchEntityDescription(SwitchEntityDescription):
    """YoLink SwitchEntityDescription."""

    exists_fn: Callable[[YoLinkDevice], bool] = lambda _: True
    value: Callable[[str], bool | None] = lambda _: None


DEVICE_TYPES: tuple[YoLinkSwitchEntityDescription, ...] = (
    YoLinkSwitchEntityDescription(
        key="state",
        device_class=SwitchDeviceClass.OUTLET,
        name="State",
        value=lambda value: value == "open",
        exists_fn=lambda device: device.device_type in [ATTR_DEVICE_OUTLET],
    ),
)

DEVICE_TYPE = [ATTR_DEVICE_OUTLET]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoLink Sensor from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][ATTR_COORDINATOR]
    devices = [
        device for device in coordinator.yl_devices if device.device_type in DEVICE_TYPE
    ]
    entities = []
    for device in devices:
        for description in DEVICE_TYPES:
            if description.exists_fn(device):
                entities.append(
                    YoLinkSwitchEntity(config_entry, coordinator, description, device)
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
        device: YoLinkDevice,
    ) -> None:
        """Init YoLink Outlet."""
        super().__init__(coordinator, device)
        self.config_entry = config_entry
        self.entity_description = description
        self._attr_unique_id = f"{device.device_id} {self.entity_description.key}"
        self._attr_name = f"{device.device_name} ({self.entity_description.name})"

    @callback
    def update_entity_state(self, state: dict) -> None:
        """Update HA Entity State."""
        self._attr_is_on = self.entity_description.value(
            state[self.entity_description.key]
        )
        self.async_write_ha_state()

    async def call_state_change(self, state: str) -> None:
        """Call setState api to change outlet state."""
        try:
            # call_device_http_api will check result, fail by raise YoLinkClientError
            await self.device.call_device_http_api("setState", {"state": state})
        except YoLinkAuthFailError as yl_auth_err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(yl_auth_err) from yl_auth_err
        except YoLinkClientError as yl_client_err:
            self.coordinator.last_update_success = False
            raise HomeAssistantError(yl_client_err) from yl_client_err
        self._attr_is_on = self.entity_description.value(state)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.call_state_change("open")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.call_state_change("close")
