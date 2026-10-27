"""Support for DynamicDomesticHotWaterProduction."""

from typing import Any, cast, override

from pyoverkiz.enums import (
    OverkizAttribute,
    OverkizCommand,
    OverkizCommandParam,
    OverkizState,
)
from pyoverkiz.models import Command

from homeassistant.components.water_heater import (
    STATE_PERFORMANCE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, STATE_ON, UnitOfTemperature

from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity


class DynamicDomesticHotWaterProduction(OverkizEntity, WaterHeaterEntity):
    """Representation of a DynamicDomesticHotWaterProduction (ogp:DomesticHotWater)."""

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.ON_OFF
    )

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Init method."""
        super().__init__(device_url, coordinator)

        self._attr_target_temperature_step = cast(
            float | None,
            self.device.attributes.get_value(
                OverkizAttribute.OGP_TARGET_TEMPERATURE_STEP
            ),
        )

        self._attr_operation_list = [STATE_OFF, STATE_ON]
        if OverkizCommandParam.BOOST in cast(
            list[str],
            self.device.attributes.get_value(OverkizAttribute.CORE_SUPPORTED_OPTIONS)
            or [],
        ):
            self._attr_operation_list.append(STATE_PERFORMANCE)

    @property
    def _is_boost_on(self) -> bool:
        """Return true if the boost option is activated."""
        return OverkizCommandParam.BOOST in cast(
            list[str],
            self.device.states.get_value(OverkizState.CORE_ACTIVATED_OPTIONS) or [],
        )

    @property
    @override
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        # The current bounds follow the limits configured on the installation.
        if (
            min_temp := self.device.states.get_value(
                OverkizState.CORE_TARGET_TEMPERATURE_CURRENT_LOWER_BOUND
            )
        ) is not None:
            return cast(float, min_temp)
        return super().min_temp

    @property
    @override
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if (
            max_temp := self.device.states.get_value(
                OverkizState.CORE_TARGET_TEMPERATURE_CURRENT_UPPER_BOUND
            )
        ) is not None:
            return cast(float, max_temp)
        return super().max_temp

    @property
    @override
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        return cast(
            float | None, self.device.states.get_value(OverkizState.CORE_TEMPERATURE)
        )

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return cast(
            float | None,
            self.device.states.get_value(OverkizState.CORE_TARGET_TEMPERATURE),
        )

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        await self.executor.async_execute_command(
            OverkizCommand.SET_TARGET_TEMPERATURE, kwargs[ATTR_TEMPERATURE]
        )

    @property
    @override
    def current_operation(self) -> str | None:
        """Return current operation."""
        match self.device.states.get_value(OverkizState.CORE_ON_OFF):
            case OverkizCommandParam.OFF:
                return STATE_OFF
            case OverkizCommandParam.ON:
                return STATE_PERFORMANCE if self._is_boost_on else STATE_ON
            case _:
                return None

    @override
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        if operation_mode == STATE_OFF:
            await self.async_turn_off()
            return

        commands: list[Command] = []

        # Boost can only be activated while hot water production is on.
        if self.current_operation == STATE_OFF:
            commands.append(Command(name=OverkizCommand.ON))

        if operation_mode == STATE_PERFORMANCE and not self._is_boost_on:
            commands.append(
                Command(
                    name=OverkizCommand.ACTIVATE_OPTION,
                    parameters=[OverkizCommandParam.BOOST],
                )
            )
        elif operation_mode == STATE_ON and self._is_boost_on:
            commands.append(
                Command(
                    name=OverkizCommand.DEACTIVATE_OPTION,
                    parameters=[OverkizCommandParam.BOOST],
                )
            )

        await self.executor.async_execute_commands(commands)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn hot water production on."""
        await self.executor.async_execute_command(OverkizCommand.ON)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn hot water production off."""
        await self.executor.async_execute_command(OverkizCommand.OFF)
