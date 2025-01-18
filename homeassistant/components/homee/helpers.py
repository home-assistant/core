"""Helper functions for the homee custom component."""

import logging

_LOGGER = logging.getLogger(__name__)


def get_name_for_enum(att_class, att_id: int) -> str:
    """Return the enum item name for a given integer."""
    try:
        item = att_class(att_id)
        attribute_name = item.name
    except ValueError:
        _LOGGER.warning("Value %s does not exist in %s", att_id, att_class.__name__)
        return "Unknown"

    return attribute_name
