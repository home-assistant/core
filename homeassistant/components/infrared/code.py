"""Conversion and comparison of infrared codes.

Codes are stored as pronto hex, the portable text format for raw IR
transmissions. Comparing a received signal to a stored code is done on the raw
timings, because a receiver never reports the exact same durations twice.
"""

from infrared_protocols.commands.pronto import ProntoCommand

from .entity import InfraredReceivedSignal

# Spaces of at least this length separate two frames of a transmission.
# Protocol leaders and bit spaces stay well below it, while the gap a remote
# leaves before repeating a frame is longer.
_FRAME_GAP = 20000
# A received burst matches a stored one when it is within this fraction of it,
# with an absolute floor so the shortest bursts are not held to an
# unrealistically tight window.
_TOLERANCE = 0.25
_TOLERANCE_FLOOR = 150


def _first_frame(timings: list[int]) -> list[int]:
    """Return the leading frame of a transmission.

    A remote repeats its frame for as long as the button is held, so only the
    first frame is a stable signature of a command. The trailing space is
    dropped: it belongs to the gap, not to the frame.
    """
    frame: list[int] = []
    for timing in timings:
        if timing < 0 and -timing >= _FRAME_GAP and frame:
            break
        frame.append(timing)
    if frame and frame[-1] < 0:
        frame.pop()
    return frame


def signal_to_code(signal: InfraredReceivedSignal) -> str:
    """Convert a received signal to a pronto hex code.

    Raises:
        ValueError: If the signal cannot be represented as a pronto code.
    """
    frame = _first_frame(signal.timings)
    if len(frame) % 2:
        # Pronto encodes burst pairs, so a frame ending on a pulse needs the
        # trailing space that separates it from the next frame.
        frame.append(-_FRAME_GAP)
    code: str = ProntoCommand.from_raw_timings(frame, signal.modulation).to_pronto_hex()
    return code


def code_to_frame(code: str) -> list[int]:
    """Return the frame a pronto hex code is matched against.

    Raises:
        ValueError: If the code is not valid pronto hex.
    """
    return _first_frame(ProntoCommand.from_pronto_hex(code).get_raw_timings())


def signal_to_frame(signal: InfraredReceivedSignal) -> list[int]:
    """Return the frame of a received signal, to match against a code."""
    return _first_frame(signal.timings)


def frames_match(received: list[int], expected: list[int]) -> bool:
    """Check whether two frames are the same transmission.

    Only the burst durations are compared. Whether a receiver reports spaces as
    negative durations - the convention - has no bearing on which command was
    sent, and a code that made the round trip through pronto always alternates.
    """
    if len(received) != len(expected):
        return False
    return all(
        abs(abs(actual) - abs(wanted))
        <= max(abs(wanted) * _TOLERANCE, _TOLERANCE_FLOOR)
        for actual, wanted in zip(received, expected, strict=True)
    )
