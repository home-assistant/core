"""Helpers for WLED."""

from wled import WLEDConnectionError, WLEDError

from homeassistant.exceptions import HomeAssistantError


def wled_exception_handler(func):
    """Decorate WLED calls to handle WLED exceptions.

    A decorator that wraps the passed in function, catches WLED errors,
    and handles the availability of the device in the data coordinator.
    """

    async def handler(self, *args, **kwargs):
        try:
            await func(self, *args, **kwargs)
            self.coordinator.async_update_listeners()

        except WLEDConnectionError as error:
            self.coordinator.last_update_success = False
            self.coordinator.async_update_listeners()
            raise HomeAssistantError("Error communicating with WLED API") from error

        except WLEDError as error:
            raise HomeAssistantError("Invalid response from WLED API") from error

    return handler
