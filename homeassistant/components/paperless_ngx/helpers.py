"""Helper function for Paperless-ngx sensors."""

from collections.abc import Callable
from typing import Any, TypeVar

from homeassistant.const import UnitOfInformation
from homeassistant.util.unit_conversion import InformationConverter

from .coordinator import PaperlessData

TState = TypeVar("TState")
TTransformed = TypeVar("TTransformed")


def build_state_fn(
    get_state: Callable[[PaperlessData], TState | None],
    transform: Callable[[TState], TTransformed] | None = None,
) -> Callable[[PaperlessData], TState | TTransformed | None]:
    """Create a function to extract and transform state and error from the status object."""

    def extractor(status: PaperlessData) -> TState | TTransformed | None:
        state = get_state(status) if get_state is not None else None

        transformed_state: TState | TTransformed | None

        if state is not None and transform is not None:
            transformed_state = transform(state)
        else:
            transformed_state = state

        return transformed_state

    return extractor


def build_attributes_fn(
    **kwargs: Callable[[PaperlessData], Any],
) -> Callable[[str, PaperlessData], dict[str, str]]:
    """Create a function to extract and transform attributes from the status object."""

    def attributes(key: str, data: PaperlessData) -> dict[str, str]:
        result = {}
        for name, fn in kwargs.items():
            value = fn(data)
            if value is not None:
                result[name] = str(value)
        return result

    return attributes


def bytes_to_gb_converter(value: int) -> float:
    """Convert bytes to gigabytes."""
    return round(
        InformationConverter().convert(
            value, UnitOfInformation.BYTES, UnitOfInformation.GIGABYTES
        ),
        2,
    )
