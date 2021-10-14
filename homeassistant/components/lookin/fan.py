"""The lookin integration fan platform."""
from __future__ import annotations

from typing import Any, Final

from aiolookin import Device, LookInHttpProtocol, Remote

from homeassistant.components.fan import SUPPORT_OSCILLATE, FanEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LookinPowerEntity
from .const import DEVICES, DOMAIN, LOOKIN_DEVICE, PROTOCOL

FAN_SUPPORT_FLAGS: Final = SUPPORT_OSCILLATE


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

    _type_class_map = {
        "04": LookinHumidifier,
        "05": LookinPurifier,
        "07": LookinFan,
    }
    for remote in devices:
        uuid = remote["UUID"]
        if cls := _type_class_map.get(remote["Type"]):
            device = await lookin_protocol.get_remote(uuid)
            entities.append(
                cls(
                    uuid=uuid,
                    lookin_protocol=lookin_protocol,
                    device=device,
                    lookin_device=lookin_device,
                )
            )

    async_add_entities(entities)


class LookinFanBase(LookinPowerEntity, FanEntity):
    _attr_should_poll = False

    def __init__(
        self,
        uuid: str,
        lookin_protocol: LookInHttpProtocol,
        device_class: str,
        device: Remote,
        lookin_device: Device,
    ) -> None:
        super().__init__(uuid, lookin_protocol, device, lookin_device)
        self._device_class = device_class
        self._attr_is_on = False

    async def async_turn_on(
        self,
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        await self._lookin_protocol.send_command(
            uuid=self._uuid, command=self._power_on_command, signal="FF"
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._lookin_protocol.send_command(
            uuid=self._uuid, command=self._power_off_command, signal="FF"
        )
        self._attr_is_on = True
        self.async_write_ha_state()


class LookinFan(LookinFanBase):
    def __init__(
        self,
        uuid: str,
        lookin_protocol: LookInHttpProtocol,
        device: Remote,
        lookin_device: Device,
    ) -> None:
        self._supported_features = FAN_SUPPORT_FLAGS
        self._oscillating: bool = False
        super().__init__(
            uuid=uuid,
            lookin_protocol=lookin_protocol,
            device_class="Fan",
            device=device,
            lookin_device=lookin_device,
        )

    @property
    def supported_features(self) -> int:
        return self._supported_features

    @property
    def oscillating(self) -> bool:
        return self._oscillating

    async def async_oscillate(self, oscillating: bool) -> None:
        await self._lookin_protocol.send_command(
            uuid=self._uuid, command="swing", signal="FF"
        )

        self._oscillating = oscillating
        self.async_write_ha_state()


class LookinHumidifier(LookinFanBase):
    def __init__(
        self,
        uuid: str,
        lookin_protocol: LookInHttpProtocol,
        device: Remote,
        lookin_device: Device,
    ) -> None:
        super().__init__(
            uuid=uuid,
            lookin_protocol=lookin_protocol,
            device_class="Humidifier",
            device=device,
            lookin_device=lookin_device,
        )

    @property
    def icon(self) -> str:
        return "mdi:water-percent"


class LookinPurifier(LookinFanBase):
    def __init__(
        self,
        uuid: str,
        lookin_protocol: LookInHttpProtocol,
        device: Remote,
        lookin_device: Device,
    ) -> None:
        super().__init__(
            uuid=uuid,
            lookin_protocol=lookin_protocol,
            device_class="Purifier",
            device=device,
            lookin_device=lookin_device,
        )

    @property
    def icon(self) -> str:
        return "mdi:water"
