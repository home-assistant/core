"""The lookin integration fan platform."""
from __future__ import annotations

from typing import Any, Final

from homeassistant.components.fan import SUPPORT_OSCILLATE, FanEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .aiolookin import Remote
from .const import DOMAIN
from .entity import LookinPowerEntity
from .models import LookinData

FAN_SUPPORT_FLAGS: Final = SUPPORT_OSCILLATE


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    lookin_data: LookinData = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    _type_class_map = {
        "04": LookinHumidifier,
        "05": LookinPurifier,
        "07": LookinFan,
    }
    for remote in lookin_data.devices:
        if not (cls := _type_class_map.get(remote["Type"])):
            continue
        uuid = remote["UUID"]
        device = await lookin_data.lookin_protocol.get_remote(uuid)
        entities.append(cls(uuid=uuid, device=device, lookin_data=lookin_data))

    async_add_entities(entities)


class LookinFanBase(LookinPowerEntity, FanEntity):
    _attr_should_poll = False

    def __init__(
        self,
        uuid: str,
        device: Remote,
        lookin_data: LookinData,
    ) -> None:
        super().__init__(uuid, device, lookin_data)
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
    """A lookin fan."""

    def __init__(
        self,
        uuid: str,
        device: Remote,
        lookin_data: LookinData,
    ) -> None:
        super().__init__(uuid, device, lookin_data)
        self._supported_features = FAN_SUPPORT_FLAGS
        self._oscillating: bool = False

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
    """A lookin humidifer."""

    @property
    def icon(self) -> str:
        return "mdi:water-percent"


class LookinPurifier(LookinFanBase):
    """A lookin air purifier."""

    @property
    def icon(self) -> str:
        return "mdi:water"
