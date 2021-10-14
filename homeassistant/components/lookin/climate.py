"""The lookin integration climate platform."""
from __future__ import annotations

from datetime import timedelta
import logging
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .aiolookin import IR_SENSOR_ID, Climate
from .const import DOMAIN
from .entity import LookinEntity
from .models import LookinData

SUPPORT_FLAGS: int = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_SWING_MODE

LOOKIN_FAN_MODE_IDX_TO_HASS: Final = [FAN_AUTO, FAN_LOW, FAN_MIDDLE, FAN_HIGH]
LOOKIN_SWING_MODE_IDX_TO_HASS: Final = [SWING_OFF, SWING_BOTH]
LOOKIN_HVAC_MODE_IDX_TO_HASS: Final = [
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
]

HASS_TO_LOOKIN_HVAC_MODE: dict[str, int] = {
    mode: idx for idx, mode in enumerate(LOOKIN_HVAC_MODE_IDX_TO_HASS)
}
HASS_TO_LOOKIN_FAN_MODE: dict[str, int] = {
    mode: idx for idx, mode in enumerate(LOOKIN_FAN_MODE_IDX_TO_HASS)
}
HASS_TO_LOOKIN_SWING_MODE: dict[str, int] = {
    mode: idx for idx, mode in enumerate(LOOKIN_SWING_MODE_IDX_TO_HASS)
}


MIN_TEMP: Final = 16
MAX_TEMP: Final = 30
TEMP_OFFSET: Final = 16
LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate platform for lookin from a config entry."""
    lookin_data: LookinData = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    for remote in lookin_data.devices:
        if remote["Type"] != "EF":
            continue
        uuid = remote["UUID"]

        async def _async_update():
            return await lookin_data.lookin_protocol.get_conditioner(uuid)

        coordinator = DataUpdateCoordinator(
            hass,
            LOGGER,
            name=f"{config_entry.title} {uuid}",
            update_method=_async_update,
            update_interval=timedelta(
                seconds=60
            ),  # Updates are pushed (fallback is polling)
        )
        await coordinator.async_refresh()
        device: Climate = coordinator.data
        entities.append(
            ConditionerEntity(
                uuid=uuid,
                device=device,
                lookin_data=lookin_data,
                coordinator=coordinator,
            )
        )

    async_add_entities(entities)


class ConditionerEntity(LookinEntity, CoordinatorEntity, ClimateEntity):
    """An aircon or heat pump."""

    _attr_temperature_unit = TEMP_CELSIUS
    _attr_supported_features: int = SUPPORT_FLAGS
    _attr_fan_modes: list[str] = LOOKIN_FAN_MODE_IDX_TO_HASS
    _attr_swing_modes: list[str] = LOOKIN_SWING_MODE_IDX_TO_HASS
    _attr_hvac_modes: list[str] = LOOKIN_HVAC_MODE_IDX_TO_HASS
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = PRECISION_WHOLE

    def __init__(
        self,
        uuid: str,
        device: Climate,
        lookin_data: LookinData,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Init the ConditionerEntity."""
        super().__init__(uuid, device, lookin_data)
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def _climate(self) -> Climate:
        return cast(Climate, self.coordinator.data)

    @property
    def current_temperature(self) -> int | None:
        """Return the current temperature."""
        return self._climate.temperature + TEMP_OFFSET

    @property
    def target_temperature(self) -> int | None:
        """Return the temperature we try to reach."""
        return self._climate.temperature + TEMP_OFFSET

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return LOOKIN_FAN_MODE_IDX_TO_HASS[self._climate.fan_mode]

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        return LOOKIN_SWING_MODE_IDX_TO_HASS[self._climate.swing_mode]

    @property
    def hvac_mode(self) -> str:
        """Return the current running hvac operation."""
        return LOOKIN_HVAC_MODE_IDX_TO_HASS[self._climate.hvac_mode]

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set the hvac mode of the device."""
        if (mode := HASS_TO_LOOKIN_HVAC_MODE.get(hvac_mode)) is None:
            return
        self._climate.hvac_mode = mode
        await self._lookin_protocol.update_conditioner(
            extra=self._climate.extra, status=self._make_status()
        )
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the temperature of the device."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        self._climate.temperature = int(temperature - TEMP_OFFSET)
        await self._lookin_protocol.update_conditioner(
            extra=self._climate.extra, status=self._make_status()
        )
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode of the device."""
        if (mode := HASS_TO_LOOKIN_FAN_MODE.get(fan_mode)) is None:
            return
        self._climate.fan_mode = mode
        await self._lookin_protocol.update_conditioner(
            extra=self._climate.extra, status=self._make_status()
        )
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode of the device."""
        if (mode := HASS_TO_LOOKIN_SWING_MODE.get(swing_mode)) is None:
            return
        self._climate.swing_mode = mode
        await self._lookin_protocol.update_conditioner(
            extra=self._climate.extra, status=self._make_status()
        )
        self.async_write_ha_state()

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

    @callback
    def _async_push_update(self, msg):
        """Process an update pushed via UDP."""
        if msg["sensor_id"] != IR_SENSOR_ID:
            return
        ir_uuid = msg["value"][:4]
        if ir_uuid != self._uuid:
            return
        LOGGER.debug("Processing push message for %s: %s", self.entity_id, msg)
        self._climate.update_from_status(msg["value"][-4:])
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Call when the entity is added to hass."""
        self.async_on_remove(
            self._lookin_udp_subs.subscribe(
                self._lookin_device.id, self._async_push_update
            )
        )
        return await super().async_added_to_hass()
