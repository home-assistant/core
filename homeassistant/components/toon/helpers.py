"""Helpers for Toon."""
import logging

from toonapi import ToonConnectionError, ToonError

_LOGGER = logging.getLogger(__name__)


def toon_exception_handler(func):
    """Decorate Toon calls to handle Toon exceptions.

    A decorator that wraps the passed in function, catches Toon errors,
    and handles the availability of the device in the data coordinator.
    """

    async def handler(self, *args, **kwargs):
        try:
            await func(self, *args, **kwargs)
            self.coordinator.update_listeners()

        except ToonConnectionError as error:
            _LOGGER.error("Error communicating with API: %s", error)
            self.coordinator.last_update_success = False
            self.coordinator.update_listeners()

        except ToonError as error:
            _LOGGER.error("Invalid response from API: %s", error)

    return handler
