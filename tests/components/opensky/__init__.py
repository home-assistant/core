"""Opensky tests."""
from unittest.mock import patch

from python_opensky import BoundingBox, StatesResponse


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
