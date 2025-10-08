"""Quirks registry."""

from __future__ import annotations

from collections.abc import Callable
import inspect
import pathlib
from typing import TYPE_CHECKING, Any, Self

from tuya_sharing import CustomerDevice

from ..const import DPCode
from ..models import EnumTypeData, IntegerTypeData, StateConversionFunction
from .climate import CommonClimateType, TuyaClimateDefinition
from .cover import CommonCoverType, TuyaCoverDefinition
from .select import CommonSelectType, TuyaSelectDefinition
from .sensor import CommonSensorType, TuyaSensorDefinition
from .switch import CommonSwitchType, TuyaSwitchDefinition

if TYPE_CHECKING:
    from .registry import QuirksRegistry


class TuyaDeviceQuirk:
    """Quirk for Tuya device."""

    _applies_to: list[tuple[str, str]]
    climate_definitions: list[TuyaClimateDefinition]
    cover_definitions: list[TuyaCoverDefinition]
    select_definitions: list[TuyaSelectDefinition]
    sensor_definitions: list[TuyaSensorDefinition]
    switch_definitions: list[TuyaSwitchDefinition]

    def __init__(self) -> None:
        """Initialize the quirk."""
        self._applies_to = []
        self.climate_definitions = []
        self.cover_definitions = []
        self.select_definitions = []
        self.sensor_definitions = []
        self.switch_definitions = []

        current_frame = inspect.currentframe()
        if TYPE_CHECKING:
            assert current_frame is not None
        caller = current_frame.f_back
        if TYPE_CHECKING:
            assert caller is not None
        self.quirk_file = pathlib.Path(caller.f_code.co_filename)
        self.quirk_file_line = caller.f_lineno

    def applies_to(self, *, category: str, product_id: str) -> Self:
        """Set the device type the quirk applies to."""
        self._applies_to.append((category, product_id))
        return self

    def register(self, registry: QuirksRegistry) -> None:
        """Register the quirk in the registry."""
        for category, product_id in self._applies_to:
            registry.register(category, product_id, self)

    def add_common_climate(
        self,
        *,
        key: str,
        common_type: CommonClimateType,
        current_temperature_state_conversion: StateConversionFunction | None = None,
        target_temperature_state_conversion: StateConversionFunction | None = None,
        target_temperature_command_conversion: StateConversionFunction | None = None,
    ) -> Self:
        """Add climate definition."""
        self.climate_definitions.append(
            TuyaClimateDefinition(
                key=key,
                common_type=common_type,
                current_temperature_state_conversion=current_temperature_state_conversion,
                target_temperature_state_conversion=target_temperature_state_conversion,
                target_temperature_command_conversion=target_temperature_command_conversion,
            )
        )
        return self

    def add_common_cover(
        self,
        *,
        key: DPCode,
        common_type: CommonCoverType,
        current_position_dp_code: DPCode | None = None,
        current_state_dp_code: DPCode | None = None,
        set_position_dp_code: DPCode | None = None,
        set_state_dp_code: DPCode | None = None,
    ) -> Self:
        """Add cover definition."""
        self.cover_definitions.append(
            TuyaCoverDefinition(
                key=key,
                common_type=common_type,
                current_position_dp_code=current_position_dp_code,
                current_state_dp_code=current_state_dp_code,
                set_position_dp_code=set_position_dp_code,
                set_state_dp_code=set_state_dp_code or key,
            )
        )
        return self

    def add_common_select(
        self,
        *,
        key: DPCode,
        common_type: CommonSelectType,
    ) -> Self:
        """Add select definition."""
        self.select_definitions.append(
            TuyaSelectDefinition(
                key=key,
                common_type=common_type,
            )
        )
        return self

    def add_common_sensor(
        self,
        *,
        key: DPCode,
        common_type: CommonSensorType,
        state_conversion: Callable[
            [CustomerDevice, EnumTypeData | IntegerTypeData | None, Any], Any
        ]
        | None = None,
    ) -> Self:
        """Add sensor definition."""
        self.sensor_definitions.append(
            TuyaSensorDefinition(
                key=key,
                common_type=common_type,
                state_conversion=state_conversion,
            )
        )
        return self

    def add_common_switch(
        self,
        *,
        key: DPCode,
        common_type: CommonSwitchType,
    ) -> Self:
        """Add switch definition."""
        self.switch_definitions.append(
            TuyaSwitchDefinition(
                key=key,
                common_type=common_type,
            )
        )
        return self
