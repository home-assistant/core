"""Base quirk definition."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import inspect
import pathlib
from typing import TYPE_CHECKING, Any, Self

from ..helpers import (
    TuyaClimateHVACMode,
    TuyaCoverDeviceClass,
    TuyaDeviceCategory,
    TuyaDPCode,
    TuyaEntityCategory,
    TuyaSensorDeviceClass,
)

if TYPE_CHECKING:
    from ..registry import QuirksRegistry


type TuyaIntegerConversionFunction = Callable[[Any, Any, Any], float]
"""Start conversion function:

    Args:
        device: The Tuya device instance (CustomerDevice).
        dptype: The DP type definition (TuyaIntegerTypeDefinition).
        value: The value to convert.
"""


@dataclass
class BaseTuyaDefinition:
    """Definition for a Tuya entity."""

    key: str
    translation_key: str | None = None
    translation_string: str | None = None
    state_translations: dict[str, str] | None = None
    device_class: str | None = None
    entity_category: str | None = None


@dataclass(kw_only=True)
class TuyaClimateDefinition(BaseTuyaDefinition):
    """Definition for a climate entity."""

    switch_only_hvac_mode: TuyaClimateHVACMode

    current_temperature_dp_code: TuyaDPCode | None = None
    current_temperature_state_conversion: TuyaIntegerConversionFunction | None = None
    target_temperature_dp_code: TuyaDPCode | None = None
    target_temperature_state_conversion: TuyaIntegerConversionFunction | None = None
    target_temperature_command_conversion: TuyaIntegerConversionFunction | None = None


@dataclass(kw_only=True)
class TuyaCoverDefinition(BaseTuyaDefinition):
    """Definition for a cover entity."""

    device_class: TuyaCoverDeviceClass | None = None

    current_state_dp_code: str | None = None
    current_position_dp_code: str | None = None
    set_position_dp_code: str | None = None


@dataclass(kw_only=True)
class TuyaSelectDefinition(BaseTuyaDefinition):
    """Definition for a select entity."""


@dataclass(kw_only=True)
class TuyaSensorDefinition(BaseTuyaDefinition):
    """Definition for a sensor entity."""

    device_class: TuyaSensorDeviceClass | None = None


@dataclass(kw_only=True)
class TuyaSwitchDefinition(BaseTuyaDefinition):
    """Definition for a switch entity."""


class TuyaDeviceQuirk:
    """Quirk for Tuya device."""

    def __init__(self) -> None:
        """Initialize the quirk."""
        self._applies_to: list[tuple[TuyaDeviceCategory, str]] = []
        self.climate_definitions: list[TuyaClimateDefinition] = []
        self.cover_definitions: list[TuyaCoverDefinition] = []
        self.select_definitions: list[TuyaSelectDefinition] = []
        self.sensor_definitions: list[TuyaSensorDefinition] = []
        self.switch_definitions: list[TuyaSwitchDefinition] = []

        current_frame = inspect.currentframe()
        if TYPE_CHECKING:
            assert current_frame is not None
        caller = current_frame.f_back
        if TYPE_CHECKING:
            assert caller is not None
        self.quirk_file = pathlib.Path(caller.f_code.co_filename)
        self.quirk_file_line = caller.f_lineno

    def applies_to(self, *, category: TuyaDeviceCategory, product_id: str) -> Self:
        """Set the device type the quirk applies to."""
        self._applies_to.append((category, product_id))
        return self

    def register(self, registry: QuirksRegistry) -> None:
        """Register the quirk in the registry."""
        for category, product_id in self._applies_to:
            registry.register(category, product_id, self)

    def add_climate(
        self,
        *,
        key: str,
        # Climate specific
        switch_only_hvac_mode: TuyaClimateHVACMode,
        current_temperature_dp_code: TuyaDPCode | None = None,
        current_temperature_state_conversion: TuyaIntegerConversionFunction
        | None = None,
        target_temperature_dp_code: TuyaDPCode | None = None,
        target_temperature_state_conversion: TuyaIntegerConversionFunction
        | None = None,
        target_temperature_command_conversion: TuyaIntegerConversionFunction
        | None = None,
    ) -> Self:
        """Add climate definition."""
        self.climate_definitions.append(
            TuyaClimateDefinition(
                key=key,
                switch_only_hvac_mode=switch_only_hvac_mode,
                current_temperature_dp_code=current_temperature_dp_code,
                current_temperature_state_conversion=current_temperature_state_conversion,
                target_temperature_dp_code=target_temperature_dp_code,
                target_temperature_state_conversion=target_temperature_state_conversion,
                target_temperature_command_conversion=target_temperature_command_conversion,
            )
        )
        return self

    def add_cover(
        self,
        *,
        key: TuyaDPCode,
        translation_key: str,
        translation_string: str,
        device_class: TuyaCoverDeviceClass | None = None,
        # Cover specific
        current_state_dp_code: TuyaDPCode | None = None,
        current_position_dp_code: TuyaDPCode | None = None,
        set_position_dp_code: TuyaDPCode | None = None,
    ) -> Self:
        """Add cover definition."""
        self.cover_definitions.append(
            TuyaCoverDefinition(
                key=key,
                translation_key=translation_key,
                translation_string=translation_string,
                device_class=device_class,
                current_state_dp_code=current_state_dp_code,
                current_position_dp_code=current_position_dp_code,
                set_position_dp_code=set_position_dp_code,
            )
        )
        return self

    def add_select(
        self,
        *,
        key: TuyaDPCode,
        translation_key: str,
        translation_string: str,
        entity_category: TuyaEntityCategory | None = None,
        # Select specific
        state_translations: dict[str, str] | None = None,
    ) -> Self:
        """Add select definition."""
        self.select_definitions.append(
            TuyaSelectDefinition(
                key=key,
                translation_key=translation_key,
                translation_string=translation_string,
                entity_category=entity_category,
                state_translations=state_translations,
            )
        )
        return self

    def add_sensor(
        self,
        *,
        key: TuyaDPCode,
        translation_key: str,
        translation_string: str,
        device_class: TuyaSensorDeviceClass | None = None,
        entity_category: TuyaEntityCategory | None = None,
        # Sensor specific
    ) -> Self:
        """Add sensor definition."""
        self.sensor_definitions.append(
            TuyaSensorDefinition(
                key=key,
                translation_key=translation_key,
                translation_string=translation_string,
                device_class=device_class,
                entity_category=entity_category,
            )
        )
        return self

    def add_switch(
        self,
        *,
        key: TuyaDPCode,
        translation_key: str,
        translation_string: str,
        entity_category: TuyaEntityCategory | None = None,
        # Switch specific
    ) -> Self:
        """Add switch definition."""
        self.switch_definitions.append(
            TuyaSwitchDefinition(
                key=key,
                translation_key=translation_key,
                translation_string=translation_string,
                entity_category=entity_category,
            )
        )
        return self
