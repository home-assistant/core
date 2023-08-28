"""Opensky tests."""
import json
from unittest.mock import patch

from python_opensky import StatesResponse

from tests.common import load_fixture


def patch_setup_entry() -> bool:
    """Patch interface."""
    return patch(
        "homeassistant.components.opensky.async_setup_entry", return_value=True
    )


def get_states_response_fixture(fixture: str) -> StatesResponse:
    """Return the states response from json."""
    json_fixture = load_fixture(fixture)
    return StatesResponse.parse_obj(json.loads(json_fixture))
