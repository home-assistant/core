"""Opensky tests."""
import json
from unittest.mock import patch

from python_opensky import BoundingBox, StatesResponse

from tests.common import load_fixture


def patch_setup_entry() -> bool:
    """Patch interface."""
    return patch(
        "homeassistant.components.opensky.async_setup_entry", return_value=True
    )


class MockOpenSky:
    """Mock object for OpenSky."""

    def __init__(self, states_fixture_cycle: list[str] = ["opensky/states.json"]):
        """Initialize mock object."""
        self._states_fixture_cycle = states_fixture_cycle
        self._states_fixture_cycle_count = 0

    async def get_states(self, bounding_box: BoundingBox) -> StatesResponse:
        """Mock get states."""
        item_num = self._states_fixture_cycle_count
        if len(self._states_fixture_cycle) != 1:
            self._states_fixture_cycle_count += 1
        return StatesResponse.parse_obj(
            json.loads(load_fixture(self._states_fixture_cycle[item_num]))
        )
