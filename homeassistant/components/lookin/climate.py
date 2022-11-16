"""The lookin integration climate platform."""
from __future__ import annotations

import logging
from typing import Any, Final, cast

from aiolookin import Climate, MeteoSensor
from aiolookin.models import UDPCommandType, UDPEvent

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MIDDLE,
    SWING_BOTH,
    SWING_OFF,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TYPE_TO_PLATFORM
from .coordinator import LookinDataUpdateCoordinator
from .entity import LookinCoordinatorEntity
from .models import LookinData

LOOKIN_FAN_MODE_IDX_TO_HASS: Final = [FAN_AUTO, FAN_LOW, FAN_MIDDLE, FAN_HIGH]
LOOKIN_SWING_MODE_IDX_TO_HASS: Final = [SWING_OFF, SWING_BOTH]
LOOKIN_HVAC_MODE_IDX_TO_HASS: Final = [
    HVACMode.OFF,
    HVACMode.AUTO,
    HVACMode.COOL,
    HVACMode.HEAT,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
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
        if TYPE_TO_PLATFORM.get(remote["Type"]) != Platform.CLIMATE:
            continue
        uuid = remote["UUID"]
        coordinator = lookin_data.device_coordinators[uuid]
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

    _attr_current_humidity: float | None = None  # type: ignore[assignment]
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_supported_features: int = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
    )
    _attr_fan_modes: list[str] = LOOKIN_FAN_MODE_IDX_TO_HASS
    _attr_swing_modes: list[str] = LOOKIN_SWING_MODE_IDX_TO_HASS
    _attr_hvac_modes: list[HVACMode] = LOOKIN_HVAC_MODE_IDX_TO_HASS
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = PRECISION_WHOLE

    def __init__(
        self,
        uuid: str,
        device: Climate,
        lookin_data: LookinData,
        coordinator: LookinDataUpdateCoordinator,
    ) -> None:
        """Init the ConditionerEntity."""
        super().__init__(coordinator, uuid, device, lookin_data)
        self._async_update_from_data()

    @property
    def _climate(self) -> Climate:
        return cast(Climate, self.coordinator.data)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
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
        lookin_index = LOOKIN_HVAC_MODE_IDX_TO_HASS
        if hvac_mode := kwargs.get(ATTR_HVAC_MODE):
            self._climate.hvac_mode = HASS_TO_LOOKIN_HVAC_MODE[hvac_mode]
        elif self._climate.hvac_mode == lookin_index.index(HVACMode.OFF):
            #
            # If the device is off, and the user didn't specify an HVAC mode
            # (which is the default when using the HA UI), the device won't turn
            # on without having an HVAC mode passed.
            #
            # We picked the hvac mode based on the current temp if its available
            # since only some units support auto, but most support either heat
            # or cool otherwise we set auto since we don't have a way to make
            # an educated guess.
            #
            meteo_data: MeteoSensor = self._meteo_coordinator.data
            if not (current_temp := meteo_data.temperature):
                self._climate.hvac_mode = lookin_index.index(HVACMode.AUTO)
            elif current_temp >= self._climate.temp_celsius:
                self._climate.hvac_mode = lookin_index.index(HVACMode.COOL)
            else:
                self._climate.hvac_mode = lookin_index.index(HVACMode.HEAT)
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
    def _async_update_meteo_from_value(self, event: UDPEvent) -> None:
        """Update temperature and humidity from UDP event."""
        self._attr_current_temperature = float(int(event.value[:4], 16)) / 10
        self._attr_current_humidity = float(int(event.value[-4:], 16)) / 10

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_from_data()
        super()._handle_coordinator_update()

    @callback
    def _async_push_update(self, event: UDPEvent) -> None:
        """Process an update pushed via UDP."""
        LOGGER.debug("Processing push message for %s: %s", self.entity_id, event)
        self._climate.update_from_status(event.value)
        self.coordinator.async_set_updated_data(self._climate)

    async def async_added_to_hass(self) -> None:
        """Call when the entity is added to hass."""
        self.async_on_remove(
            self._lookin_udp_subs.subscribe_event(
                self._lookin_device.id,
                UDPCommandType.ir,
                self._uuid,
                self._async_push_update,
            )
        )
        self.async_on_remove(
            self._lookin_udp_subs.subscribe_event(
                self._lookin_device.id,
                UDPCommandType.meteo,
                None,
                self._async_update_meteo_from_value,
            )
        )
        return await super().async_added_to_hass()
