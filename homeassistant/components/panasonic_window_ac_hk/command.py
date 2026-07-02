"""Wrap the pure-Python encoder as an infrared-protocols Command.

The Home Assistant ``infrared`` platform sends ``infrared_protocols.Command``
objects to emitters, which read ``command.modulation`` (carrier Hz) and
``command.get_raw_timings()`` (signed microsecond list). This adapter exposes
our Panasonic CW frames in that shape.
"""

from infrared_protocols.commands import Command

from . import encoder


class PanasonicWindowAcHKCommand(Command):  # type: ignore[misc]
    """An IR command for a Panasonic HK/Macau window A/C (CW-HU/HZ/SU/SUL)."""

    def __init__(self, state: list[int]) -> None:
        """Wrap a pre-built 27-byte full frame or 16-byte short frame."""
        super().__init__(modulation=encoder.CARRIER_HZ, repeat_count=0)
        self._state = state

    @classmethod
    def full(
        cls,
        *,
        off: bool = False,
        mode: str,
        temp: float,
        fan: str,
        swing: str,
        nanoex: bool,
    ) -> PanasonicWindowAcHKCommand:
        """Build a full state command (power/mode/temp/fan/swing/nanoeX)."""
        return cls(
            encoder.build_full_frame(
                off=off, mode=mode, temp=temp, fan=fan, swing=swing, nanoex=nanoex
            )
        )

    @classmethod
    def short(cls, kind: str) -> PanasonicWindowAcHKCommand:
        """Build a Quiet/Powerful toggle command."""
        return cls(encoder.build_short_frame(kind))

    def get_raw_timings(self) -> list[int]:
        """Return signed microsecond timings (positive pulse, negative space)."""
        return encoder.frame_to_timings(self._state)
