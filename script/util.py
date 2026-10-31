"""Utility functions for the scaffold script."""

import argparse

from .const import COMPONENT_DIR


def valid_integration(integration):
    """Test if it's a valid integration."""
    if not (COMPONENT_DIR / integration).exists():
        raise argparse.ArgumentTypeError(
            f"The integration {integration} does not exist."
        )

    return integration
