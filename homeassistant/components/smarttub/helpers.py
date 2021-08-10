"""Helper functions for SmartTub integration."""

import smarttub


def get_spa_name(spa: smarttub.Spa) -> str:
    """Return the name of the specified spa."""
    return f"{spa.brand} {spa.model}"
