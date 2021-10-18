"""Helpers for WLED."""

from wled import WLEDConnectionError, WLEDError

from .const import LOGGER


def wled_exception_handler(func):
    """Decorate WLED calls to handle WLED exceptions.

    A decorator that wraps the passed in function, catches WLED errors,
    and handles the availability of the device in the data coordinator.
    """

    async def handler(self, *args, **kwargs):
        try:
            await func(self, *args, **kwargs)
            self.coordinator.update_listeners()

        except WLEDConnectionError as error:
            LOGGER.error("Error communicating with API: %s", error)
            self.coordinator.last_update_success = False
            self.coordinator.update_listeners()

        except WLEDError as error:
            LOGGER.error("Invalid response from API: %s", error)

    return handler
