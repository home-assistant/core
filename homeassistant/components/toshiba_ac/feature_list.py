"""Include helpers for converting enums to strings."""

from enum import Enum
import logging
from typing import Any, TypeVar

from toshiba_ac.utils import pretty_enum_name

_LOGGER = logging.getLogger(__name__)


def get_feature_list(feature_list: list[Any]) -> list[str]:
    """Return a list of features supported by the device."""
    return [pretty_enum_name(e) for e in feature_list if pretty_enum_name(e) != "None"]


T = TypeVar("T", bound=Enum)


def get_feature_by_name(feature_list: list[T], feature_name: str) -> T | None:
    """Return the enum value of that item with the given name from a feature list."""
    _LOGGER.debug("searching %s for %s", feature_list, feature_name)

    feature_list = [e for e in feature_list if pretty_enum_name(e) == feature_name]
    _LOGGER.debug("and found %s", feature_list)

    if len(feature_list) > 0:
        return feature_list[0]
    return None
