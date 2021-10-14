"""The lookin integration climate platform."""
from __future__ import annotations

from typing import Any, Final, cast

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MIDDLE,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SWING_BOTH,
    SWING_OFF,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .aiolookin import Climate
from .const import DOMAIN
from .entity import LookinEntity
from .models import LookinData

SUPPORT_FLAGS: int = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_SWING_MODE

STATE_TO_HVAC_MODE: dict[str, int] = {
    HVAC_MODE_OFF: 0,
    HVAC_MODE_AUTO: 1,
    HVAC_MODE_COOL: 2,
    HVAC_MODE_HEAT: 3,
    HVAC_MODE_DRY: 4,
    HVAC_MODE_FAN_ONLY: 5,
}

STATE_TO_FAN_MODE: dict[str, int] = {
    FAN_AUTO: 0,
    FAN_LOW: 1,
    FAN_MIDDLE: 2,
    FAN_HIGH: 3,
}

STATE_TO_SWING_MODE: dict[str, int] = {SWING_OFF: 0, SWING_BOTH: 1}

MIN_TEMP: Final = 16
MAX_TEMP: Final = 30
TEMP_OFFSET: Final = 16


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    lookin_data: LookinData = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    for remote in lookin_data.devices:
        if remote["Type"] != "EF":
            continue
        uuid = remote["UUID"]
        device = await lookin_data.lookin_protocol.get_conditioner(uuid)
        entities.append(
            ConditionerEntity(
                uuid=uuid,
                device=device,
                lookin_data=lookin_data,
            )
        )

    async_add_entities(entities)


class ConditionerEntity(LookinEntity, ClimateEntity):
    _attr_supported_features: int = SUPPORT_FLAGS
    _attr_fan_modes: list[str] = [FAN_AUTO, FAN_LOW, FAN_MIDDLE, FAN_HIGH]
    _attr_swing_modes: list[str] = [SWING_OFF, SWING_BOTH]
    _attr_hvac_modes: list[str] = [
        HVAC_MODE_OFF,
        HVAC_MODE_AUTO,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT,
        HVAC_MODE_DRY,
        HVAC_MODE_FAN_ONLY,
    ]

    def __init__(
        self,
        uuid: str,
        device: Climate,
        lookin_data: LookinData,
    ) -> None:
        super().__init__(uuid, device, lookin_data)
        self._attr_temperature_unit = TEMP_CELSIUS
        self._attr_min_temp = MIN_TEMP
        self._attr_max_temp = MAX_TEMP
        self._attr_target_temperature_step = PRECISION_WHOLE

    @property
    def _climate(self):
        return cast(Climate, self._device)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        if (mode := STATE_TO_HVAC_MODE.get(hvac_mode)) is None:
            return

        self._climate.hvac_mode = mode

        await self._lookin_protocol.update_conditioner(
            extra=self._climate.extra, status=self._make_status()
        )

    @property
    def current_temperature(self) -> int | None:
        return self._climate.temperature + TEMP_OFFSET

    @property
    def target_temperature(self) -> int | None:
        return self._climate.temperature + TEMP_OFFSET

    @property
    def fan_mode(self) -> str | None:
        return self._attr_fan_modes[self._climate.fan_mode]

    @property
    def swing_mode(self) -> str | None:
        return self._attr_swing_modes[self._climate.swing_mode]

    @property
    def hvac_mode(self) -> str:
        return self._attr_hvac_modes[self._climate.hvac_mode]

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if temperature is None:
            return

        self._climate.temperature = int(temperature - TEMP_OFFSET)

        await self._lookin_protocol.update_conditioner(
            extra=self._climate.extra, status=self._make_status()
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:

        if (mode := STATE_TO_FAN_MODE.get(fan_mode)) is None:
            return

        self._climate.fan_mode = mode

        await self._lookin_protocol.update_conditioner(
            extra=self._climate.extra, status=self._make_status()
        )

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        if (mode := STATE_TO_SWING_MODE.get(swing_mode)) is None:
            return

        self._climate.swing_mode = mode

        await self._lookin_protocol.update_conditioner(
            extra=self._climate.extra, status=self._make_status()
        )

    async def async_update(self) -> None:
        self._device = await self._lookin_protocol.get_conditioner(self._uuid)

    @staticmethod
    def _int_to_hex(i: int) -> str:
        return f"{i + TEMP_OFFSET:X}"[1]

    def _make_status(self) -> str:
        return (
            f"{self._climate.hvac_mode}"
            f"{self._int_to_hex(self._climate.temperature)}"
            f"{self._climate.fan_mode}"
            f"{self._climate.swing_mode}"
        )
