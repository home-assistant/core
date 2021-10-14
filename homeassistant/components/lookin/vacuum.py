"""The lookin integration vacuum platform."""
from __future__ import annotations

from typing import Any

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

from .aiolookin import Remote
from .const import DOMAIN
from .entity import LookinPowerEntity
from .models import LookinData

SUPPORT_FLAGS: int = SUPPORT_TURN_ON | SUPPORT_TURN_OFF


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    lookin_data: LookinData = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    for remote in lookin_data.devices:
        if remote["Type"] != "06":
            continue
        uuid = remote["UUID"]
        device = await lookin_data.lookin_protocol.get_remote(uuid)
        entities.append(
            LookinVacuum(
                uuid=uuid,
                device=device,
                lookin_data=lookin_data,
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
        device: Remote,
        lookin_data: LookinData,
    ) -> None:
        super().__init__(uuid, device, lookin_data)
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
