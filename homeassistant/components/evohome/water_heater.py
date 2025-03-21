"""Support for WaterHeater entities of the Evohome integration."""

from __future__ import annotations

import logging
from typing import Any

import evohomeasync2 as evo
from evohomeasync2.const import SZ_STATE_STATUS, SZ_TEMPERATURE_STATUS
from evohomeasync2.schemas.const import DhwState as EvoDhwState, ZoneMode as EvoZoneMode

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import (
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    STATE_OFF,
    STATE_ON,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import EVOHOME_KEY
from .coordinator import EvoDataUpdateCoordinator
from .entity import EvoChild

_LOGGER = logging.getLogger(__name__)

STATE_AUTO = "auto"

HA_STATE_TO_EVO = {STATE_AUTO: "", STATE_ON: EvoDhwState.ON, STATE_OFF: EvoDhwState.OFF}
EVO_STATE_TO_HA = {v: k for k, v in HA_STATE_TO_EVO.items() if k != ""}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Create a DHW controller."""
    if discovery_info is None:
        return

    coordinator = hass.data[EVOHOME_KEY].coordinator
    tcs = hass.data[EVOHOME_KEY].tcs

    assert tcs.hotwater is not None  # mypy check

    _LOGGER.debug(
        "Adding: DhwController (%s), id=%s",
        tcs.hotwater.type,
        tcs.hotwater.id,
    )

    entity = EvoDHW(coordinator, tcs.hotwater)

    async_add_entities([entity])

    await entity.update_attrs()


class EvoDHW(EvoChild, WaterHeaterEntity):
    """Base for any evohome-compatible DHW controller."""

    _attr_name = "DHW controller"
    _attr_icon = "mdi:thermometer-lines"
    _attr_operation_list = list(HA_STATE_TO_EVO)
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    _evo_device: evo.HotWater
    _evo_id_attr = "dhw_id"
    _evo_state_attr_names = (SZ_STATE_STATUS, SZ_TEMPERATURE_STATUS)

    def __init__(
        self, coordinator: EvoDataUpdateCoordinator, evo_device: evo.HotWater
    ) -> None:
        """Initialize an evohome-compatible DHW controller."""

        super().__init__(coordinator, evo_device)
        self._evo_id = evo_device.id

        self._attr_unique_id = evo_device.id
        self._attr_name = evo_device.name  # is static

        self._attr_precision = (
            PRECISION_TENTHS if coordinator.client_v1 else PRECISION_WHOLE
        )
        self._attr_supported_features = (
            WaterHeaterEntityFeature.AWAY_MODE | WaterHeaterEntityFeature.OPERATION_MODE
        )

    @property
    def current_operation(self) -> str | None:
        """Return the current operating mode (Auto, On, or Off)."""
        if self._evo_device.mode == EvoZoneMode.FOLLOW_SCHEDULE:
            return STATE_AUTO
        return EVO_STATE_TO_HA[self._evo_device.state]

    @property
    def is_away_mode_on(self) -> bool | None:
        """Return True if away mode is on."""
        is_off = EVO_STATE_TO_HA[self._evo_device.state] == STATE_OFF
        is_permanent = self._evo_device.mode == EvoZoneMode.PERMANENT_OVERRIDE
        return is_off and is_permanent

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode for a DHW controller.

        Except for Auto, the mode is only until the next SetPoint.
        """
        if operation_mode == STATE_AUTO:
            await self.coordinator.call_client_api(self._evo_device.reset())
        else:
            await self._update_schedule()
            until = self.setpoints.get("next_sp_from")
            until = dt_util.as_utc(until) if until else None

            if operation_mode == STATE_ON:
                await self.coordinator.call_client_api(self._evo_device.on(until=until))
            else:  # STATE_OFF
                await self.coordinator.call_client_api(
                    self._evo_device.off(until=until)
                )

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        await self.coordinator.call_client_api(self._evo_device.off())

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        await self.coordinator.call_client_api(self._evo_device.reset())

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self.coordinator.call_client_api(self._evo_device.on())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.coordinator.call_client_api(self._evo_device.off())
