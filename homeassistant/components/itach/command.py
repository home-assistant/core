"""Command parsing helpers for the legacy iTach remote platform."""

from dataclasses import dataclass

# Pronto learned-code timing unit in microseconds.
PRONTO_FREQUENCY_REFERENCE_US = 0.241246


@dataclass(frozen=True, slots=True)
class RawTiming:
    """One raw IR mark/space timing pair in microseconds."""

    high_us: int
    low_us: int


class CommandParseError(ValueError):
    """Raised when a legacy iTach IR command cannot be parsed."""


class ParsedItachCommand:
    """Parsed legacy iTach command data.

    The legacy YAML remote platform stores command data as learned Pronto hex.
    Keep this command-like object close to the virtual_remote command parser so
    the same parsed representation can be used when sending through pyitach or a
    future Home Assistant infrared entity.
    """

    def __init__(self, *, modulation: int, timings: list[int]) -> None:
        """Initialize parsed command."""
        self.modulation = modulation
        self._timings = timings

    def get_raw_timings(self) -> list[RawTiming]:
        """Return raw timings as mark/space pairs."""
        return [
            RawTiming(high_us=high_us, low_us=low_us)
            for high_us, low_us in zip(
                self._timings[::2],
                self._timings[1::2],
                strict=True,
            )
        ]


def parse_pronto_command(command: str) -> ParsedItachCommand:
    """Parse learned raw Pronto hex into an iTach command.

    This supports raw learned Pronto codes beginning with 0000. Once and repeat
    sections are flattened into one raw timing sequence.
    """
    modulation, timings = _parse_pronto_command(command.strip())
    _validate_raw_command(modulation, timings)
    return ParsedItachCommand(modulation=modulation, timings=timings)


def _parse_pronto_command(command: str) -> tuple[int, list[int]]:
    """Parse learned raw Pronto hex into carrier frequency and timings."""
    if not command:
        raise _command_error("Command cannot be empty")

    words = command.split()
    if not _looks_like_pronto(words):
        raise _command_error(
            "Only learned raw Pronto commands beginning with 0000 are supported"
        )

    values = [int(word, 16) for word in words]
    if len(values) < 6:
        raise _command_error("Pronto command is too short")

    pronto_type = values[0]
    frequency_word = values[1]
    once_pairs = values[2]
    repeat_pairs = values[3]
    timing_words = values[4:]
    pair_count = once_pairs + repeat_pairs
    expected_timing_words = pair_count * 2

    if pronto_type != 0x0000:
        raise _command_error(
            "Only learned raw Pronto commands beginning with 0000 are supported"
        )

    if frequency_word <= 0:
        raise _command_error("Pronto frequency word must be greater than zero")

    if pair_count <= 0:
        raise _command_error("Pronto command must declare at least one timing pair")

    if len(timing_words) != expected_timing_words:
        raise _command_error(
            "Pronto command timing word count does not match the declared lengths"
        )

    if any(word <= 0 for word in timing_words):
        raise _command_error("Pronto timing words must be greater than zero")

    modulation = round(1_000_000 / (frequency_word * PRONTO_FREQUENCY_REFERENCE_US))
    timings = [
        round(word * frequency_word * PRONTO_FREQUENCY_REFERENCE_US)
        for word in timing_words
    ]
    return modulation, timings


def _looks_like_pronto(words: list[str]) -> bool:
    """Return whether words look like raw Pronto hex."""
    if len(words) < 4:
        return False
    return all(_is_hex_word(word) for word in words) and words[0].lower() == "0000"


def _is_hex_word(word: str) -> bool:
    """Return whether a string is a 16-bit Pronto-style hex word."""
    if len(word) != 4:
        return False
    try:
        int(word, 16)
    except ValueError:
        return False
    return True


def _validate_raw_command(modulation: int, timings: list[int]) -> None:
    """Validate raw remote command fields."""
    if modulation <= 0:
        raise _command_error("modulation must be greater than zero")

    if not timings:
        raise _command_error("timings cannot be empty")

    if len(timings) % 2 != 0:
        raise _command_error("timings must contain mark/space pairs")

    if any(timing <= 0 for timing in timings):
        raise _command_error("timings must be greater than zero")


def _command_error(error: str) -> CommandParseError:
    """Build a command parser error."""
    return CommandParseError(error)
