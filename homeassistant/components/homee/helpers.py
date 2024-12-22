"""Helper functions for the homee custom component."""

import logging

from pyHomee import Homee
from pyHomee.model import HomeeNode

_LOGGER = logging.getLogger(__name__)


def get_imported_nodes(config_entry) -> list[HomeeNode]:
    """Get a list of nodes that should be imported."""
    homee: Homee = config_entry.runtime_data
    return homee.nodes


def get_name_for_enum(att_class, att_id) -> str:
    """Return the enum item name for a given integer."""
    try:
        attribute_name = att_class(att_id).name
    except ValueError:
        _LOGGER.warning("Value %s does not exist in %s", att_id, att_class.__name__)
        return "Unknown"

    return attribute_name
