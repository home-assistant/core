"""Utility functions for Dreo integration."""

from collections.abc import Callable
import logging
from typing import TypeVar

from hscloud.hscloudexception import HsCloudBusinessException, HsCloudException

from homeassistant.exceptions import ConfigEntryNotReady

_LOGGER = logging.getLogger(__name__)
T = TypeVar("T")


def handle_api_exceptions(func: Callable[[], T]) -> T:
    """Handle common API exceptions for Dreo integration.

    Args:
        func: Function to execute that may raise exceptions

    Returns:
        Result of the function call

    Raises:
        ConfigEntryNotReady: If connection or authentication fails

    """
    try:
        return func()
    except HsCloudException as ex:
        _LOGGER.exception("Unable to connect")
        raise ConfigEntryNotReady("unable to connect") from ex
    except HsCloudBusinessException as ex:
        _LOGGER.exception("Invalid username or password")
        raise ConfigEntryNotReady("invalid username or password") from ex
