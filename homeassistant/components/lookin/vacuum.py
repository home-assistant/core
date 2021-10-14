"""The lookin integration vacuum platform."""
from __future__ import annotations

from typing import Any

from aiolookin import Device, LookInHttpProtocol, Remote

from homeassistant.components.vacuum import (
    SERVICE_START,
    SERVICE_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    VacuumEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LookinPowerEntity
from .const import DEVICES, DOMAIN, LOOKIN_DEVICE, PROTOCOL

SUPPORT_FLAGS: int = SUPPORT_TURN_ON | SUPPORT_TURN_OFF


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][config_entry.entry_id]
    lookin_protocol = data[PROTOCOL]
    lookin_device = data[LOOKIN_DEVICE]
    devices = data[DEVICES]

    entities = []

    for remote in devices:
        if remote["Type"] == "06":
            uuid = remote["UUID"]
            device = await lookin_protocol.get_remote(uuid)
            entities.append(
                LookinVacuum(
                    uuid=uuid,
                    lookin_protocol=lookin_protocol,
                    device=device,
                    lookin_device=lookin_device,
                )
            )

    async_add_entities(entities, update_before_add=True)


class LookinVacuum(LookinPowerEntity, VacuumEntity):
    _attr_should_poll = False
    _attr_supported_features = SUPPORT_FLAGS
    _attr_assumed_state = True

    def __init__(
        self,
        uuid: str,
        lookin_protocol: LookInHttpProtocol,
        device: Remote,
        lookin_device: Device,
    ) -> None:
        super().__init__(uuid, lookin_protocol, device, lookin_device)
        self._status = SERVICE_STOP

    @property
    def is_on(self) -> bool:
        return self._status != SERVICE_STOP

    @property
    def status(self) -> str:
        return self._status

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._lookin_protocol.send_command(
            uuid=self._uuid, command=self._power_on_command, signal="FF"
        )
        self._status = SERVICE_START
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._lookin_protocol.send_command(
            uuid=self._uuid, command=self._power_off_command, signal="FF"
        )
        self._status = SERVICE_STOP
        self.async_write_ha_state()
