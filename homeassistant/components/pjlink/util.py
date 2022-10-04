"""Common PJLink utilities and types."""

from typing import TypedDict


def format_input_source(input_source_name: str, input_source_number: int) -> str:
    """Format input source for display in UI."""
    return f"{input_source_name} {input_source_number}"


class LampStateType(TypedDict):
    """Lamp state typed definition."""

    state: bool
    hours: int
