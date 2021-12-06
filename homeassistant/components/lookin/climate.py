"""The lookin integration climate platform."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from typing import Any, Final, cast

from aiolookin import Climate, MeteoSensor, SensorID

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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .entity import LookinCoordinatorEntity
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

        def _wrap_async_update(
            uuid: str,
        ) -> Callable[[], Coroutine[None, Any, Climate]]:
            """Create a function to capture the uuid cell variable."""

            async def _async_update() -> Climate:
                return await lookin_data.lookin_protocol.get_conditioner(uuid)

            return _async_update

        coordinator = DataUpdateCoordinator(
            hass,
            LOGGER,
            name=f"{config_entry.title} {uuid}",
            update_method=_wrap_async_update(uuid),
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


class ConditionerEntity(LookinCoordinatorEntity, ClimateEntity):
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
        super().__init__(coordinator, uuid, device, lookin_data)
        self._async_update_from_data()

    @property
    def _climate(self) -> Climate:
        return cast(Climate, self.coordinator.data)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set the hvac mode of the device."""
        if (mode := HASS_TO_LOOKIN_HVAC_MODE.get(hvac_mode)) is None:
            return
        self._climate.hvac_mode = mode
        await self._async_update_conditioner()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the temperature of the device."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        self._climate.temp_celsius = int(temperature)
        await self._async_update_conditioner()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode of the device."""
        if (mode := HASS_TO_LOOKIN_FAN_MODE.get(fan_mode)) is None:
            return
        self._climate.fan_mode = mode
        await self._async_update_conditioner()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode of the device."""
        if (mode := HASS_TO_LOOKIN_SWING_MODE.get(swing_mode)) is None:
            return
        self._climate.swing_mode = mode
        await self._async_update_conditioner()

    async def _async_update_conditioner(self) -> None:
        """Update the conditioner state from the climate data."""
        self.coordinator.async_set_updated_data(self._climate)
        await self._lookin_protocol.update_conditioner(climate=self._climate)

    def _async_update_from_data(self) -> None:
        """Update attrs from data."""
        meteo_data: MeteoSensor = self._meteo_coordinator.data
        self._attr_current_temperature = meteo_data.temperature
        self._attr_current_humidity = int(meteo_data.humidity)
        self._attr_target_temperature = self._climate.temp_celsius
        self._attr_fan_mode = LOOKIN_FAN_MODE_IDX_TO_HASS[self._climate.fan_mode]
        self._attr_swing_mode = LOOKIN_SWING_MODE_IDX_TO_HASS[self._climate.swing_mode]
        self._attr_hvac_mode = LOOKIN_HVAC_MODE_IDX_TO_HASS[self._climate.hvac_mode]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_from_data()
        super()._handle_coordinator_update()

    @callback
    def _async_push_update(self, msg: dict[str, str]) -> None:
        """Process an update pushed via UDP."""
        LOGGER.debug("Processing push message for %s: %s", self.entity_id, msg)
        self._climate.update_from_status(msg["value"])
        self.coordinator.async_set_updated_data(self._climate)

    async def async_added_to_hass(self) -> None:
        """Call when the entity is added to hass."""
        self.async_on_remove(
            self._lookin_udp_subs.subscribe_sensor(
                self._lookin_device.id, SensorID.IR, self._uuid, self._async_push_update
            )
        )
        self.async_on_remove(
            self._meteo_coordinator.async_add_listener(self._handle_coordinator_update)
        )
        return await super().async_added_to_hass()
