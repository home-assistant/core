"""Quirks registry."""

from __future__ import annotations

from dataclasses import dataclass
import inspect
import pathlib
from typing import TYPE_CHECKING, Self

from .homeassistant import (
    TuyaCoverDeviceClass,
    TuyaEntityCategory,
    TuyaSensorDeviceClass,
)

if TYPE_CHECKING:
    from .registry import QuirksRegistry


@dataclass
class BaseTuyaDefinition:
    """Definition for a Tuya entity."""

    key: str
    translation_key: str
    translation_string: str
    device_class: str | None = None
    entity_category: str | None = None


@dataclass(kw_only=True)
class TuyaCoverDefinition(BaseTuyaDefinition):
    """Definition for a cover entity."""

    device_class: TuyaCoverDeviceClass | None = None

    current_state_dp_code: str | None = None
    current_position_dp_code: str | None = None
    set_position_dp_code: str | None = None


@dataclass(kw_only=True)
class TuyaSensorDefinition(BaseTuyaDefinition):
    """Definition for a sensor entity."""

    device_class: TuyaSensorDeviceClass | None = None


class TuyaDeviceQuirk:
    """Quirk for Tuya device."""

    _applies_to: list[tuple[str, str]]
    cover_definitions: list[TuyaCoverDefinition]
    sensor_definitions: list[TuyaSensorDefinition]

    def __init__(self) -> None:
        """Initialize the quirk."""
        self._applies_to = []
        self.cover_definitions = []
        self.sensor_definitions = []

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

    def add_cover(
        self,
        *,
        key: str,
        translation_key: str,
        translation_string: str,
        device_class: TuyaCoverDeviceClass | None = None,
        # Cover specific
        current_state_dp_code: str | None = None,
        current_position_dp_code: str | None = None,
        set_position_dp_code: str | None = None,
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

    def add_sensor(
        self,
        *,
        key: str,
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
