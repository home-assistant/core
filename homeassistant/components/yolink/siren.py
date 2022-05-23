"""YoLink Siren."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yolink.device import YoLinkDevice
from yolink.exception import YoLinkAuthFailError, YoLinkClientError

from homeassistant.components.siren import (
    SirenEntity,
    SirenEntityDescription,
    SirenEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_COORDINATOR, ATTR_DEVICE_SIREN, DOMAIN
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


@dataclass
class YoLinkSirenEntityDescription(SirenEntityDescription):
    """YoLink SirenEntityDescription."""

    exists_fn: Callable[[YoLinkDevice], bool] = lambda _: True
    value: Callable[[str], bool | None] = lambda _: None


DEVICE_TYPES: tuple[YoLinkSirenEntityDescription, ...] = (
    YoLinkSirenEntityDescription(
        key="state",
        name="State",
        value=lambda value: value == "alert",
        exists_fn=lambda device: device.device_type in [ATTR_DEVICE_SIREN],
    ),
)

DEVICE_TYPE = [ATTR_DEVICE_SIREN]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoLink siren from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][ATTR_COORDINATOR]
    devices = [
        device for device in coordinator.yl_devices if device.device_type in DEVICE_TYPE
    ]
    entities = []
    for device in devices:
        for description in DEVICE_TYPES:
            if description.exists_fn(device):
                entities.append(
                    YoLinkSirenEntity(config_entry, coordinator, description, device)
                )
    async_add_entities(entities)


class YoLinkSirenEntity(YoLinkEntity, SirenEntity):
    """YoLink Siren Entity."""

    entity_description: YoLinkSirenEntityDescription

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
        description: YoLinkSirenEntityDescription,
        device: YoLinkDevice,
    ) -> None:
        """Init YoLink Siren."""
        super().__init__(coordinator, device)
        self.config_entry = config_entry
        self.entity_description = description
        self._attr_unique_id = f"{device.device_id} {self.entity_description.key}"
        self._attr_name = f"{device.device_name} ({self.entity_description.name})"
        self._attr_supported_features = (
            SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF
        )

    @callback
    def update_entity_state(self, state: dict) -> None:
        """Update HA Entity State."""
        self._attr_is_on = self.entity_description.value(
            state[self.entity_description.key]
        )
        self.async_write_ha_state()

    async def call_state_change(self, state: bool) -> None:
        """Call setState api to change outlet state."""
        try:
            # call_device_http_api will check result, fail by raise YoLinkClientError
            await self.device.call_device_http_api(
                "setState", {"state": {"alarm": state}}
            )
        except YoLinkAuthFailError as yl_auth_err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(yl_auth_err) from yl_auth_err
        except YoLinkClientError as yl_client_err:
            self.coordinator.last_update_success = False
            raise HomeAssistantError(yl_client_err) from yl_client_err
        self._attr_is_on = self.entity_description.value("alert" if state else "normal")
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.call_state_change(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.call_state_change(False)
