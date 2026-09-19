"""Tests for the raw HTTP request checker."""

from pathlib import Path

import astroid
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.http_library import HassEnforceHttpLibraryChecker
from pylint_home_assistant.http_library_exemptions import GRANDFATHERED_DOMAINS
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker

_COMPONENTS_PATH = Path(__file__).parents[2] / "homeassistant" / "components"


@pytest.fixture(name="http_library_checker")
def http_library_checker_fixture(
    linter: UnittestLinter,
) -> HassEnforceHttpLibraryChecker:
    """Fixture to provide a raw HTTP request checker."""
    return HassEnforceHttpLibraryChecker(linter)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param("import requests\n\nrequests.get(url)", id="requests_get"),
        pytest.param("import requests\n\nrequests.Session()", id="requests_session"),
        pytest.param("import requests as req\n\nreq.post(url)", id="requests_aliased"),
        pytest.param("import httpx\n\nhttpx.get(url)", id="httpx_get"),
        pytest.param("import httpx\n\nhttpx.AsyncClient()", id="httpx_async_client"),
        pytest.param(
            "import aiohttp\n\naiohttp.ClientSession()", id="aiohttp_own_session"
        ),
        pytest.param(
            "import aiohttp\n\naiohttp.request('GET', url)", id="aiohttp_request"
        ),
        pytest.param("from requests import get\n\nget(url)", id="from_requests_get"),
        pytest.param(
            "from aiohttp import ClientSession\n\nClientSession()",
            id="from_aiohttp_client_session",
        ),
        pytest.param(
            "import aiohttp.web\n\naiohttp.ClientSession()",
            id="aiohttp_web_import_still_flags_client",
        ),
    ],
)
def test_flagged(
    linter: UnittestLinter,
    http_library_checker: HassEnforceHttpLibraryChecker,
    code: str,
) -> None:
    """Test raw requests that should be flagged."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    walk_checker(linter, http_library_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "hass-integration-raw-http-client"


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            "from aiohttp import ClientSession\n\n"
            "def f(session: ClientSession) -> None: ...",
            id="client_session_type_hint",
        ),
        pytest.param(
            "import aiohttp\n\ndef f(session: aiohttp.ClientSession) -> None: ...",
            id="client_session_type_hint_attribute",
        ),
        pytest.param(
            "from aiohttp import ClientError\n\n"
            "try:\n    pass\nexcept ClientError:\n    pass",
            id="catch_client_error",
        ),
        pytest.param("import httpx\n\nx: httpx.Response = resp", id="httpx_type_hint"),
        pytest.param(
            "from aiohttp import web\n\nweb.Application()", id="aiohttp_web_server"
        ),
        pytest.param(
            "session = async_get_clientsession(hass)\nsession.get(url)",
            id="injected_session_get",
        ),
        pytest.param(
            "import my_device_library\n\nmy_device_library.get(url)", id="library"
        ),
    ],
)
def test_not_flagged(
    linter: UnittestLinter,
    http_library_checker: HassEnforceHttpLibraryChecker,
    code: str,
) -> None:
    """Test usages that should not be flagged."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")

    with assert_no_messages(linter):
        walk_checker(linter, http_library_checker, root_node)


def test_reports_library_name(
    linter: UnittestLinter,
    http_library_checker: HassEnforceHttpLibraryChecker,
) -> None:
    """Test that the offending library name is included in the message."""
    root_node = astroid.parse(
        "import requests\n\nrequests.get(url)", "homeassistant.components.pylint_test"
    )
    http_library_checker.visit_module(root_node)
    http_library_checker.visit_import(root_node.body[0])
    call_node = root_node.body[1].value

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="hass-integration-raw-http-client",
            node=call_node,
            args=("requests",),
            line=3,
            col_offset=0,
            end_line=3,
            end_col_offset=17,
        ),
    ):
        http_library_checker.visit_call(call_node)


def test_grandfathered_domain_ignored(
    linter: UnittestLinter,
    http_library_checker: HassEnforceHttpLibraryChecker,
) -> None:
    """Test that grandfathered integrations are not flagged."""
    root_node = astroid.parse(
        "import requests\n\nrequests.get(url)", "homeassistant.components.abode"
    )

    with assert_no_messages(linter):
        walk_checker(linter, http_library_checker, root_node)


def test_non_integration_module_ignored(
    linter: UnittestLinter,
    http_library_checker: HassEnforceHttpLibraryChecker,
) -> None:
    """Test that non-integration modules are ignored."""
    root_node = astroid.parse(
        "import requests\n\nrequests.get(url)", "tests.components.pylint_test"
    )

    with assert_no_messages(linter):
        walk_checker(linter, http_library_checker, root_node)


def test_grandfathered_domains_exist() -> None:
    """Test that every grandfathered domain is an existing integration."""
    missing = sorted(
        domain
        for domain in GRANDFATHERED_DOMAINS
        if not (_COMPONENTS_PATH / domain).is_dir()
    )
    assert not missing, f"Grandfathered domains without an integration: {missing}"
