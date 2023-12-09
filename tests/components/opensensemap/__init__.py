"""OpenSenseMap tests."""
import re
from unittest.mock import AsyncMock, patch

from opensensemap_api import OpenSenseMap
from opensensemap_api.exceptions import OpenSenseMapError

from tests.common import load_json_object_fixture

VALID_STATION_ID = "6107df25c4aab8001b94e043"
VALID_STATION_NAME = "Stadtbücherei Münster"


def patch_opensensemap_get_data() -> AsyncMock:
    """Patch actual api call from server."""

    async def get_fixture_data(self):
        provided_station_id = re.search(r"\/([^/]*)$", self.base_url).group(1)
        to_take = "valid" if provided_station_id == VALID_STATION_ID else "invalid"
        self.data = load_json_object_fixture(f"opensensemap/{to_take}.json")

    mock = patch.object(OpenSenseMap, "get_data", get_fixture_data)
    return mock


def patch_opensensemap_connection_failed() -> AsyncMock:
    """Patch api call to raise can't connect error."""
    return patch.object(OpenSenseMap, "get_data", side_effect=OpenSenseMapError)


def patch_setup_entry() -> AsyncMock:
    """Patch interface."""
    return patch(
        "homeassistant.components.opensensemap.async_setup_entry", return_value=True
    )
