"""Command parsing helpers for remote platform virtual remotes."""

from dataclasses import dataclass
import json
import re
from typing import Any

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

DEFAULT_CARRIER_FREQUENCY = 38_000


@dataclass(frozen=True, slots=True)
class RawTiming:
    """One raw IR mark/space timing pair in microseconds."""

    high_us: int
    low_us: int


class CommandParseError(ValueError):
    """Raised when a persisted or service-provided IR command cannot be parsed."""


class RawInfraredCommand:
    """Raw infrared command accepted by Home Assistant infrared emitters.

    The Home Assistant infrared platform currently expects command-like objects
    with a ``modulation`` attribute and ``get_raw_timings()`` method. Avoiding a
    runtime subclass import keeps command parsing usable even when optional
    infrared protocol dependencies are not importable during test collection.
    """

    def __init__(self, *, modulation: int, timings: list[int]) -> None:
        """Initialize raw command."""
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


def parse_remote_command(
    raw_command: str,
    kwargs: dict[str, Any] | None = None,
    *,
    translation_domain: str = DOMAIN,
) -> RawInfraredCommand:
    """Parse a remote command payload into an infrared command.

    Supported payloads:
    - JSON timing array, or JSON object with ``timings`` plus optional
      ``modulation``/``carrier_frequency``
    - raw Pronto hex beginning with ``0000``
    - text timings: ``100,200,300,400`` or ``38000:100,200``

    Parser internals raise :class:`CommandParseError`; this public Home
    Assistant boundary converts parse failures to translated
    :class:`HomeAssistantError` instances for callers and tests that use this
    helper directly.
    """
    try:
        return _parse_remote_command(raw_command, kwargs)
    except CommandParseError as err:
        raise HomeAssistantError(
            translation_domain=translation_domain,
            translation_key="remote_invalid_command",
            translation_placeholders={"error": str(err)},
        ) from err


def validate_remote_command_payload(raw_command: str) -> None:
    """Validate a persisted remote command payload.

    Options flow validation needs the raw parser error so it can attach the
    validation failure to the command field instead of surfacing a service-style
    HomeAssistantError.
    """
    _parse_remote_command(raw_command, {})


def _parse_remote_command(
    raw_command: str,
    kwargs: dict[str, Any] | None = None,
) -> RawInfraredCommand:
    """Parse a remote command payload into an infrared command."""
    kwargs = kwargs or {}
    modulation = _default_modulation(kwargs)
    command = raw_command.strip()

    if not command:
        raise _command_error("Command cannot be empty")

    if command.startswith(("{", "[")):
        modulation, timings = _parse_json_command(command, modulation)
    elif _looks_like_pronto(command):
        modulation, timings = _parse_pronto_command(command)
    else:
        modulation, timings = _parse_text_command(command, modulation)

    validate_raw_command(modulation, timings)
    return RawInfraredCommand(modulation=modulation, timings=timings)


def _default_modulation(kwargs: dict[str, Any]) -> int:
    """Return modulation from kwargs, or the default carrier frequency."""
    value = kwargs.get("modulation")
    if value is None:
        value = kwargs.get("carrier_frequency")
    if value is None:
        value = DEFAULT_CARRIER_FREQUENCY

    return _coerce_int(value, "modulation")


def _parse_json_command(command: str, default_modulation: int) -> tuple[int, list[int]]:
    """Parse a JSON remote command payload.

    Supported JSON forms:

    - bare timing array: ``[9000, 4500, 560, 560]``
    - object with timings: ``{"timings": [9000, 4500, 560, 560]}``
    - object with timings and modulation/carrier_frequency override
    """
    try:
        payload = json.loads(command)
    except json.JSONDecodeError as err:
        raise _command_error("Command JSON is invalid") from err

    if isinstance(payload, list):
        return default_modulation, _coerce_int_list(payload, "timings")

    if not isinstance(payload, dict):
        raise _command_error("Command JSON must be an object or timing array")

    raw_modulation = payload.get("modulation")
    if raw_modulation is None:
        raw_modulation = payload.get("carrier_frequency")
    if raw_modulation is None:
        raw_modulation = default_modulation

    modulation = _coerce_int(raw_modulation, "modulation")

    timings = _coerce_int_list(payload.get("timings"), "timings")
    return modulation, timings


def _parse_text_command(command: str, default_modulation: int) -> tuple[int, list[int]]:
    """Parse a raw timing text remote command payload."""
    modulation = default_modulation
    timings_text = command

    if ":" in command:
        modulation_text, timings_text = command.split(":", 1)
        try:
            modulation = int(modulation_text.strip())
        except ValueError as err:
            raise _command_error("Command modulation must be an integer") from err

    return modulation, _coerce_int_list(
        [token for token in re.split(r"[\s,]+", timings_text.strip()) if token],
        "timings",
    )


def _looks_like_pronto(command: str) -> bool:
    """Return whether a command looks like raw Pronto hex."""
    words = command.split()
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


def _parse_pronto_command(command: str) -> tuple[int, list[int]]:
    """Parse learned raw Pronto hex into carrier frequency and timings.

    This supports raw learned Pronto codes beginning with 0000. Once and repeat
    sections are flattened into one raw timing sequence.
    """
    values = [int(word, 16) for word in command.split()]
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

    modulation = round(1_000_000 / (frequency_word * 0.241246))
    timings = [round(word * frequency_word * 0.241246) for word in timing_words]
    return modulation, timings


def _coerce_int(value: Any, field: str) -> int:
    """Coerce a value to an integer without truncating malformed input."""
    if isinstance(value, bool):
        raise _command_error(f"{field} must be an integer")

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as err:
            raise _command_error(f"{field} must be an integer") from err

    raise _command_error(f"{field} must be an integer")


def _coerce_int_list(value: Any, field: str) -> list[int]:
    """Coerce a sequence of values to integers."""
    if not isinstance(value, (list, tuple)):
        raise _command_error(f"{field} must be a list")

    result: list[int] = []
    for item in value:
        if not str(item).strip():
            raise _command_error(f"{field} must not contain empty values")
        try:
            result.append(_coerce_int(item, field))
        except CommandParseError as err:
            raise _command_error(f"{field} must contain only integers") from err

    return result


def validate_raw_command(modulation: int, timings: list[int]) -> None:
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
