"""Soma helpers functions."""

import logging

_LOGGER = logging.getLogger(__name__)


def log_device_unreachable(name: str, msg: str):
    """Log device unreachable."""
    _LOGGER.error("Unable to reach device %s (%s).", name, msg)


def log_connect_api_unreachable():
    """Log Soma Connect api unreachable."""
    _LOGGER.error("Connection to SOMA Connect failed!")


def log_debug_msg(debugMsg: str):
    """Log debug message."""
    _LOGGER.debug(debugMsg)


def is_api_response_success(apiResponse: dict) -> bool:
    """Check if the response returned from the Connect API is a success or not."""
    return ("result" in apiResponse) and (apiResponse["result"].lower() == "success")
