"""Helper functions for the homee custom component."""

from enum import IntEnum
import logging

_LOGGER = logging.getLogger(__name__)


def get_name_for_enum(att_class: type[IntEnum], att_id: int) -> str | None:
    """Return the enum item name for a given integer."""
    try:
        item = att_class(att_id)
    except ValueError:
        _LOGGER.warning("Value %s does not exist in %s", att_id, att_class.__name__)
        return None
    return item.name.lower()
