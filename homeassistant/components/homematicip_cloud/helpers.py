"""Helper functions for Homematicip Cloud Integration."""

from functools import wraps
import json
import logging

from homeassistant.exceptions import HomeAssistantError

from . import HomematicipGenericEntity

_LOGGER = logging.getLogger(__name__)


def is_error_response(response) -> bool:
    """Response from async call contains errors or not."""
    if isinstance(response, dict):
        return response.get("errorCode") not in ("", None)

    return False


def handle_errors(func):
    """Handle async errors."""

    @wraps(func)
    async def inner(self: HomematicipGenericEntity) -> None:
        """Handle errors from async call."""
        result = await func(self)
        if is_error_response(result):
            _LOGGER.error(
                "Error while execute function %s: %s",
                __name__,
                json.dumps(result),
            )
            raise HomeAssistantError(
                f"Error while execute function {func.__name__}: {result.get('errorCode')}. See log for more information."
            )

    return inner
