"""Opensky tests."""
from typing import Any
from unittest.mock import patch

from aiohttp import BasicAuth
from python_opensky import BoundingBox, StatesResponse
from python_opensky.exceptions import OpenSkyUnauthenticatedError


def patch_setup_entry() -> bool:
    """Patch interface."""
    return patch(
        "homeassistant.components.opensky.async_setup_entry", return_value=True
    )


class MockOpenSky:
    """Mock object for OpenSky."""

    async def get_states(self, bounding_box: BoundingBox) -> StatesResponse:
        """Mock get states."""
        return StatesResponse(states=[], time=0)

    async def authenticate(self, auth: BasicAuth, contributing_user: bool) -> None:
        """Mock authenticate."""
        pass

    async def __aenter__(self) -> "MockOpenSky":
        """Async enter."""
        return self

    async def __aexit__(self, *_exc_info: Any) -> None:
        """Async exit."""


class NonAuthenticatedMockOpenSky(MockOpenSky):
    """Mock object for OpenSky that is not authenticated."""

    async def authenticate(self, auth: BasicAuth, contributing_user: bool) -> None:
        """Mock authenticate."""
        raise OpenSkyUnauthenticatedError()
