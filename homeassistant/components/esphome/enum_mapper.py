"""Helper class to convert between Home Assistant and ESPHome enum values."""

from typing import overload

from aioesphomeapi import APIIntEnum


class EsphomeEnumMapper[_EnumT: APIIntEnum, _ValT]:
    """Helper class to convert between hass and esphome enum values."""

    def __init__(self, mapping: dict[_EnumT, _ValT]) -> None:
        """Construct a EsphomeEnumMapper."""
        # Add none mapping
        augmented_mapping: dict[_EnumT | None, _ValT | None] = mapping  # type: ignore[assignment]
        augmented_mapping[None] = None

        self._mapping = augmented_mapping
        self._inverse: dict[_ValT, _EnumT] = {v: k for k, v in mapping.items()}

    @overload
    def from_esphome(self, value: _EnumT) -> _ValT: ...

    @overload
    def from_esphome(self, value: _EnumT | None) -> _ValT | None: ...

    def from_esphome(self, value: _EnumT | None) -> _ValT | None:
        """Convert from an esphome int representation to a hass string."""
        return self._mapping[value]

    def from_hass(self, value: _ValT) -> _EnumT:
        """Convert from a hass string to a esphome int representation."""
        return self._inverse[value]
