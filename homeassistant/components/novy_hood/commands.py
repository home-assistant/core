"""Radio-frequency commands for the Novy hood remote.

Prototype: these four `RadioFrequencyCommand` subclasses live inside the
integration rather than being loaded from `rf_protocols.get_codes(...)`.
Once the protocol is validated on real hardware, they will be extracted
into the `home-assistant-libs/rf-protocols` library.

## Decoding notes

The timings below were derived from Broadlink RF learned blobs of the
user's Novy 4-button remote (+, -, light, power). The blobs were
base64-decoded, the 4-byte Broadlink wrapper (`0xb1 0xc0 len_lo len_hi`)
stripped, and the pulse stream walked with the standard convention that
a `0x00` byte marks a 16-bit big-endian duration and any other byte is a
single-byte duration in 32.84 µs units. Broadlink RF-sweep telemetry
(huge > 1 ms spikes and short ~130 µs stepper runs) was discarded; the
remaining pulses were split on inter-frame gaps (>= 5 ms of space) and
quantized to either the short bit unit (~394 µs) or the long bit unit
(~788 µs). All payload frames within each capture quantized identically,
so the derived timings are confidently canonical.

## Protocol summary

- Carrier: 433.92 MHz OOK.
- Preamble: 8000 µs mark + 6300 µs space (taken from the one capture -
  `power` - that included it; the others omitted the preamble because
  Broadlink's learn mode started mid-burst).
- Bit-pair duration unit: short (`S`) = 394 µs, long (`L`) = 788 µs.
- Payload: 25 durations for `plus`/`minus`, 37 durations for
  `light`/`power`, alternating mark/space, always ending on a mark.
- Inter-frame gap: each frame is suffixed with ~10 ms of space so that
  the RF driver can cleanly repeat it.
- Observed pulse patterns (paired as mark+space, excluding the trailing
  mark):
    plus : (SS)(LL)(SS)(LL)(SS)(LL)(SS)(LL)(SS)(LL)(SS)(LL)  + S
    minus: (SS)(LL)(SS)(LL)(SS)(LL)(SS)(LL)(SS)(LL)(SL)(SS)  + L
    light: (SS)(LL)(SS)(LL)(SS)(LL)(SS)(LL)(SS)(LL)(SL)(SL)
           (SS)(LL)(SS)(LS)(LS)(LL)                          + S
    power: (SS)(LL)(SS)(LL)(SS)(LL)(SS)(LL)(SS)(LL)(SL)(SL)
           (SS)(LL)(SS)(LS)(LL)(SL)                          + S
  The bit-encoding semantics (which combination of S/L is a `0` vs a
  `1`) have not been fully reverse-engineered; for the prototype we
  transmit the exact captured pulse train rather than synthesizing
  frames from a bit payload.

## Repeat count

`repeat_count = 8` means the RF driver sends the frame 9 times in total
(repeat_count is *additional* transmits). This is a conservative choice
- the captured blobs' Broadlink header byte `0xc0` (= 192) is a
Broadlink-level repeat field, not a per-frame count, so it does not
directly translate. Real-hardware reliability will tell us whether to
dial this up or down.
"""

from __future__ import annotations

from rf_protocols import ModulationType, RadioFrequencyCommand

FREQUENCY = 433_920_000
REPEAT_COUNT = 8

_PLUS_TIMINGS: list[int] = [
    8000,
    -6300,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -10000,
]

_MINUS_TIMINGS: list[int] = [
    8000,
    -6300,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -788,
    394,
    -394,
    788,
    -10000,
]

_LIGHT_TIMINGS: list[int] = [
    8000,
    -6300,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -788,
    394,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -394,
    788,
    -394,
    788,
    -788,
    394,
    -10000,
]

_POWER_TIMINGS: list[int] = [
    8000,
    -6300,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -788,
    394,
    -788,
    394,
    -394,
    788,
    -788,
    394,
    -394,
    788,
    -394,
    788,
    -788,
    394,
    -788,
    394,
    -10000,
]


class _NovyHoodCommand(RadioFrequencyCommand):
    """Base for Novy hood RF commands."""

    _timings: list[int]

    def __init__(self) -> None:
        """Initialize the command."""
        super().__init__(
            frequency=FREQUENCY,
            modulation=ModulationType.OOK,
            repeat_count=REPEAT_COUNT,
        )

    def get_raw_timings(self) -> list[int]:
        """Return the raw pulse timings."""
        return list(self._timings)


class NovyHoodPlus(_NovyHoodCommand):
    """`+` button: increase fan level by one."""

    _timings = _PLUS_TIMINGS


class NovyHoodMinus(_NovyHoodCommand):
    """`-` button: decrease fan level by one."""

    _timings = _MINUS_TIMINGS


class NovyHoodLight(_NovyHoodCommand):
    """Light button: toggle the cooker-hood light."""

    _timings = _LIGHT_TIMINGS


class NovyHoodPower(_NovyHoodCommand):
    """Power button: semantics unknown on the user's hood; exposed for experimentation."""

    _timings = _POWER_TIMINGS
