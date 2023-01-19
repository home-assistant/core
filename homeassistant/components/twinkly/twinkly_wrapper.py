"""Simple wrapper for the Twinkly API."""
from __future__ import annotations

import logging
from typing import Any

from ttls.client import Twinkly

from .const import TWINKLY_RETURN_CODE, TWINKLY_RETURN_CODE_OK
from .exceptions import TwinklyError

_LOGGER = logging.getLogger(__name__)


class TwinklyWrapper(Twinkly):
    """Wrap Twinkly to validate responses."""

    def _valid_response(
        self, response: dict[Any, Any], check_for: str | None = None
    ) -> dict[Any, Any]:
        """Validate twinkly-responses from the API."""
        if (
            response
            and response.get(TWINKLY_RETURN_CODE) == TWINKLY_RETURN_CODE_OK
            and (not check_for or check_for in response)
        ):
            _LOGGER.debug("Twinkly response: %s", response)
            return response
        raise TwinklyError(f"Invalid response from Twinkly: {response}")

    async def get_saved_movies(self):
        """Get saved movies."""
        return self._valid_response(
            await super().get_saved_movies(), check_for="movies"
        )

    async def get_current_movie(self):
        """Get current active movie."""
        return self._valid_response(await super().get_current_movie())

    async def get_current_colour(self):
        """Get current set color."""
        return self._valid_response(await super().get_current_colour())
