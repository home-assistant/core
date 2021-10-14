"""The lookin integration light platform."""
from __future__ import annotations

from typing import Any

from aiolookin import Device, LookInHttpProtocol, Remote

from homeassistant.components.light import COLOR_MODE_ONOFF, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LookinPowerEntity
from .const import DEVICES, DOMAIN, LOOKIN_DEVICE, PROTOCOL


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][config_entry.entry_id]
    lookin_device = data[LOOKIN_DEVICE]
    lookin_protocol = data[PROTOCOL]
    devices = data[DEVICES]

    entities = []

    for remote in devices:
        if remote["Type"] == "03":
            uuid = remote["UUID"]
            device = await lookin_protocol.get_remote(uuid)
            entities.append(
                LookinLightEntity(
                    uuid=uuid,
                    lookin_protocol=lookin_protocol,
                    device=device,
                    lookin_device=lookin_device,
                )
            )

    async_add_entities(entities, update_before_add=True)


class LookinLightEntity(LookinPowerEntity, LightEntity):

    _attr_supported_color_modes = {COLOR_MODE_ONOFF}
    _attr_color_mode = COLOR_MODE_ONOFF
    _attr_assumed_state = True
    _attr_should_poll = False

    def __init__(
        self,
        uuid: str,
        lookin_protocol: LookInHttpProtocol,
        device: Remote,
        lookin_device: Device,
    ) -> None:
        super().__init__(uuid, lookin_protocol, device, lookin_device)
        self._attr_is_on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._lookin_protocol.send_command(
            uuid=self._uuid, command=self._power_on_command, signal="FF"
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._lookin_protocol.send_command(
            uuid=self._uuid, command=self._power_off_command, signal="FF"
        )
        self._attr_is_on = False
        self.async_write_ha_state()
