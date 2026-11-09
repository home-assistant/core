"""Tests for the direct HTTP request checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint_home_assistant.checkers.direct_http_request import (
    HassDirectHttpRequestChecker,
)
import pytest

from . import assert_no_messages, walk_checker


@pytest.fixture(name="direct_http_request_checker")
def direct_http_request_checker_fixture(
    linter: UnittestLinter,
) -> HassDirectHttpRequestChecker:
    """Fixture to provide a direct HTTP request checker."""
    return HassDirectHttpRequestChecker(linter)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param(
            """
import requests

def update(url):
    return requests.get(url, timeout=10)
""",
            "requests.get",
            id="requests_module_function",
        ),
        pytest.param(
            """
from requests import post as do_post

def update(url):
    return do_post(url, timeout=10)
""",
            "requests.post",
            id="requests_function_imported_with_alias",
        ),
        pytest.param(
            """
import requests

def update(request):
    return requests.Session().send(request)
""",
            "requests.Session().send",
            id="requests_session_send",
        ),
        pytest.param(
            """
import aiohttp

async def update(url):
    async with aiohttp.request("GET", url) as resp:
        return await resp.text()
""",
            "aiohttp.request",
            id="aiohttp_request_function",
        ),
        pytest.param(
            """
import httpx2

async def update(url):
    return httpx2.get(url)
""",
            "httpx2.get",
            id="httpx2_module_function",
        ),
        pytest.param(
            """
from homeassistant.helpers.aiohttp_client import async_get_clientsession

async def update(hass, url):
    session = async_get_clientsession(hass)
    return await session.get(url)
""",
            "session.get",
            id="async_get_clientsession_variable",
        ),
        pytest.param(
            """
from homeassistant.helpers import aiohttp_client

async def update(hass, url):
    return await aiohttp_client.async_get_clientsession(hass).post(url)
""",
            "aiohttp_client.async_get_clientsession(hass).post",
            id="async_get_clientsession_namespace_import",
        ),
        pytest.param(
            """
from homeassistant.helpers.httpx_client import get_async_client

async def update(hass, url):
    client = get_async_client(hass)
    return await client.stream("GET", url)
""",
            "client.stream",
            id="httpx_helper_client",
        ),
        pytest.param(
            """
import aiohttp

async def update(url):
    async with (
        aiohttp.ClientSession() as session,
        session.get(url) as resp,
    ):
        return await resp.text()
""",
            "session.get",
            id="session_bound_in_same_with",
        ),
        pytest.param(
            """
from aiohttp import ClientSession

async def update(session: ClientSession, url):
    return await session.ws_connect(url)
""",
            "session.ws_connect",
            id="annotated_argument",
        ),
        pytest.param(
            """
from aiohttp import ClientSession

async def update(url, *, session: ClientSession | None = None):
    return await session.get(url)
""",
            "session.get",
            id="annotated_optional_keyword_argument",
        ),
        pytest.param(
            """
from homeassistant.helpers.aiohttp_client import async_get_clientsession

class Api:
    def __init__(self, hass):
        self._session = async_get_clientsession(hass)

    async def update(self, url):
        return await self._session.get(url)
""",
            "self._session.get",
            id="instance_attribute",
        ),
        pytest.param(
            """
from aiohttp import ClientSession

class Api:
    def __init__(self, session: ClientSession):
        self._session = session

    async def update(self, url):
        return await self._session.put(url)
""",
            "self._session.put",
            id="instance_attribute_from_annotated_argument",
        ),
        pytest.param(
            """
from dataclasses import dataclass
from aiohttp import ClientSession

@dataclass
class Api:
    session: ClientSession

    async def update(self, url):
        return await self.session.delete(url)
""",
            "self.session.delete",
            id="dataclass_field",
        ),
    ],
)
def test_direct_http_request(
    linter: UnittestLinter,
    direct_http_request_checker: HassDirectHttpRequestChecker,
    code: str,
    expected: str,
) -> None:
    """Test HTTP requests made directly by an integration are flagged."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test.api")
    walk_checker(linter, direct_http_request_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-direct-http-request"
    assert messages[0].args == (expected,)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
import aiohttp
import requests

async def update(api):
    try:
        return await api.update()
    except (aiohttp.ClientError, requests.RequestException):
        return None
""",
            id="catching_exceptions",
        ),
        pytest.param(
            """
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from mylib import Api

async def setup(hass):
    return Api(session=async_get_clientsession(hass))
""",
            id="passing_session_to_library",
        ),
        pytest.param(
            """
async def setup(hass, data):
    hass.states.get("light.kitchen")
    return data.get("key")
""",
            id="get_on_other_objects",
        ),
        pytest.param(
            """
from homeassistant.helpers.aiohttp_client import async_get_clientsession

async def setup(hass):
    session = async_get_clientsession(hass)
    return session.closed
""",
            id="non_request_attribute",
        ),
        pytest.param(
            """
from .api import get

async def setup(url):
    return await get(url)
""",
            id="relative_import",
        ),
    ],
)
def test_no_message(
    linter: UnittestLinter,
    direct_http_request_checker: HassDirectHttpRequestChecker,
    code: str,
) -> None:
    """Test code that does not make an HTTP request is not flagged."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test.api")

    with assert_no_messages(linter):
        walk_checker(linter, direct_http_request_checker, root_node)


@pytest.mark.parametrize(
    "module_name",
    [
        pytest.param("homeassistant.components.rest.data", id="allowed_integration"),
        pytest.param("homeassistant.helpers.aiohttp_client", id="helper"),
        pytest.param("tests.components.pylint_test.test_init", id="test"),
    ],
)
def test_outside_scope(
    linter: UnittestLinter,
    direct_http_request_checker: HassDirectHttpRequestChecker,
    module_name: str,
) -> None:
    """Test modules outside of the checked integrations are not flagged."""
    root_node = astroid.parse(
        """
import requests

def update(url):
    return requests.get(url, timeout=10)
""",
        module_name,
    )

    with assert_no_messages(linter):
        walk_checker(linter, direct_http_request_checker, root_node)
