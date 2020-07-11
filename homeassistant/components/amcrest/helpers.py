"""Helpers for amcrest component."""
import logging

from .const import DOMAIN


def service_signal(service, *args):
    """Encode signal."""
    return "_".join([DOMAIN, service, *args])


def log_update_error(logger, action, name, entity_type, error, level=logging.ERROR):
    """Log an update error."""
    logger.log(
        level,
        "Could not %s %s %s due to error: %s",
        action,
        name,
        entity_type,
        error.__class__.__name__,
    )
