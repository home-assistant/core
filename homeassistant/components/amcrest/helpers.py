"""Helpers for amcrest component."""
from .const import DOMAIN


def service_signal(service, ident=None):
    """Encode service and identifier into signal."""
    signal = f"{DOMAIN}_{service}"
    if ident:
        signal += f"_{ident.replace('.', '_')}"
    return signal


def log_update_error(logger, action, name, entity_type, error):
    """Log an update error."""
    logger.error(
        "Could not %s %s %s due to error: %s",
        action,
        name,
        entity_type,
        error.__class__.__name__,
    )
