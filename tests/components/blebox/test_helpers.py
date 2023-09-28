"""Blebox helpers tests."""

from aiohttp.helpers import BasicAuth
import pytest

from homeassistant.components.blebox.helpers import (
    get_maybe_authenticated_session,
    get_non_empty_key,
)
from homeassistant.core import HomeAssistant

DICT_SAMPLE = {"a": "", "b": "value"}
DICT_TEST_PARAMETERS = [("a", None), ("b", "value")]

USERNAME = "user"
PASSWORD = "password"

SESSION_TEST_PARAMS = [
    ("", "", None),
    ("user", "password", BasicAuth),
]


async def test_get_maybe_authenticated_session_none(
    hass: HomeAssistant, param=SESSION_TEST_PARAMS[0]
):
    """Tests if session auth is None."""
    session = get_maybe_authenticated_session(
        hass=hass, username=param[0], password=param[1]
    )
    assert session.auth is param[2]


async def test_get_maybe_authenticated_session_auth(
    hass: HomeAssistant, param=SESSION_TEST_PARAMS[1]
):
    """Tests if session have BasicAuth."""
    session = get_maybe_authenticated_session(
        hass=hass, username=param[0], password=param[1]
    )
    assert isinstance(session.auth, param[2])


@pytest.mark.parametrize("param", DICT_TEST_PARAMETERS)
async def test_get_non_empty_key(param):
    """Tests if method returns None for empty string."""
    value = get_non_empty_key(DICT_SAMPLE, param[0])
    assert value == param[1]
