"""Support for Tesla cars."""
from functools import wraps
import logging
from teslajsonpy.exceptions import IncompleteCredentials

from . import TeslaDevice

_LOGGER = logging.getLogger(__name__)


def check_for_reauth(func):
    """Wrap a Tesla device function to check for need to reauthenticate."""

    @wraps(func)
    async def wrapped(*args):
        result = None
        self_object = None
        if isinstance(args[0], TeslaDevice):
            self_object = args[0]
        try:
            await func(*args)
        except IncompleteCredentials:
            if self_object and self_object._config_entry_id:
                _LOGGER.debug(
                    "Reauth needed for %s after calling: %s",
                    self_object,
                    func,
                )
                await self_object.hass.config_entries.async_reload(
                    self_object._config_entry_id
                )
            return None
        return result

    return wrapped
