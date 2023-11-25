"""Opensky tests."""
from unittest.mock import patch

from python_opensky import StatesResponse

from tests.common import load_json_object_fixture


def patch_setup_entry() -> bool:
    """Patch interface."""
    return patch(
        "homeassistant.components.opensky.async_setup_entry", return_value=True
    )


def get_states_response_fixture(fixture: str) -> StatesResponse:
    """Return the states response from json."""
    states_json = load_json_object_fixture(fixture)
    return StatesResponse.from_api(states_json)
