"""Tests for infrared code conversion and matching."""

from infrared_protocols.commands import Command
from infrared_protocols.commands.nec import NECCommand
from infrared_protocols.commands.rc5 import RC5Command
from infrared_protocols.commands.rc6 import RC6Command
from infrared_protocols.commands.samsung import Samsung32Command
from infrared_protocols.commands.sony import SonyCommand
import pytest

from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.components.infrared.code import (
    code_to_frame,
    frames_match,
    signal_to_code,
    signal_to_frame,
)

PROTOCOLS = [
    pytest.param(NECCommand(address=0x04FB, command=0xF7), id="nec"),
    pytest.param(RC5Command(address=0x05, command=0x0A), id="rc5"),
    pytest.param(RC6Command(address=0x05, command=0x0A), id="rc6"),
    pytest.param(SonyCommand(address=0x05, address_bits=5, command=0x0A), id="sony"),
    pytest.param(Samsung32Command(address=0x05, command=0x0A), id="samsung32"),
]


def _received(command: Command, *, jitter: float = 0.0) -> InfraredReceivedSignal:
    """Return the signal a receiver reports, off by `jitter` on every burst.

    The bursts are stretched and squeezed in turn, the worst case a receiver
    reporting a transmission inaccurately can produce.
    """
    return InfraredReceivedSignal(
        timings=[
            round(timing * (1 + (jitter if index % 2 else -jitter)))
            for index, timing in enumerate(command.get_raw_timings())
        ],
        modulation=command.modulation,
    )


@pytest.mark.parametrize("command", PROTOCOLS)
@pytest.mark.parametrize("jitter", [0.0, 0.1])
def test_captured_code_matches_the_command_it_was_captured_from(
    command: Command, jitter: float
) -> None:
    """Test a captured code still matches when the receiver is off by 10%."""
    code = signal_to_code(_received(command))

    assert frames_match(
        signal_to_frame(_received(command, jitter=jitter)), code_to_frame(code)
    )


@pytest.mark.parametrize(
    "other",
    [
        pytest.param(NECCommand(address=0x04FB, command=0xF6), id="other_button"),
        pytest.param(NECCommand(address=0x0102, command=0xF7), id="other_remote"),
        pytest.param(RC5Command(address=0x05, command=0x0A), id="other_protocol"),
    ],
)
def test_captured_code_does_not_match_another_command(other: Command) -> None:
    """Test a captured code does not match a different command."""
    code = signal_to_code(_received(NECCommand(address=0x04FB, command=0xF7)))

    assert not frames_match(signal_to_frame(_received(other)), code_to_frame(code))


def test_only_the_first_frame_is_matched() -> None:
    """Test a held button matches the code captured from a single press."""
    code = signal_to_code(_received(NECCommand(address=0x04FB, command=0xF7)))
    held = _received(NECCommand(address=0x04FB, command=0xF7, repeat_count=3))

    assert len(signal_to_frame(held)) == len(code_to_frame(code))
    assert frames_match(signal_to_frame(held), code_to_frame(code))


def test_signal_without_timings_cannot_be_captured() -> None:
    """Test a signal that carries no bursts is rejected."""
    with pytest.raises(ValueError, match="at least one burst pair"):
        signal_to_code(InfraredReceivedSignal(timings=[]))


def test_code_that_is_not_pronto_hex_is_rejected() -> None:
    """Test a code that is not pronto hex is rejected."""
    with pytest.raises(ValueError, match="pronto words must be 4 hex digits"):
        code_to_frame("not pronto")
