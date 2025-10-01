"""Quirks registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from .homeassistant import TuyaCoverDeviceClass

if TYPE_CHECKING:
    from .registry import QuirksRegistry


@dataclass
class BaseTuyaDefinition:
    """Definition for a Tuya device."""

    key: str
    translation_key: str
    translation_string: str


@dataclass(kw_only=True)
class TuyaCoverDefinition(BaseTuyaDefinition):
    """Definition for a cover device."""

    device_class: TuyaCoverDeviceClass | None = None

    current_state_dp_code: str | None = None
    current_position_dp_code: str | None = None
    set_position_dp_code: str | None = None


@dataclass
class DeviceQuirk:
    """Quirk for Tuya device."""

    _applies_to: list[tuple[str, str]]
    cover_definitions: list[TuyaCoverDefinition]

    def __init__(self) -> None:
        """Initialize the quirk."""
        self._applies_to = []
        self.cover_definitions = []

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
        current_state_dp_code: str | None = None,
        current_position_dp_code: str | None = None,
        set_position_dp_code: str | None = None,
    ) -> Self:
        """Add cover quirk."""
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
