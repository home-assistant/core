"""Test Droplet services."""

import logging

from homeassistant.core import ServiceCall

logger = logging.getLogger(__name__)


def handle_flow_rate(call: ServiceCall):
    """Handle message."""
    logger.error("hiiii")
    logger.error(str(call.data["state"]))
