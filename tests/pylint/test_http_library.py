"""Tests for the raw HTTP client library checker."""

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
    """Fixture to provide a raw HTTP client library checker."""
    return HassEnforceHttpLibraryChecker(linter)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param("import requests", id="import_requests"),
        pytest.param("import httpx", id="import_httpx"),
        pytest.param("import aiohttp", id="import_aiohttp"),
        pytest.param("import aiohttp.client", id="import_aiohttp_submodule"),
        pytest.param("from requests import get", id="from_requests"),
        pytest.param("from httpx import AsyncClient", id="from_httpx"),
        pytest.param("from aiohttp import ClientSession", id="from_aiohttp_client"),
        pytest.param(
            "from aiohttp import web, ClientError", id="from_aiohttp_web_and_client"
        ),
        pytest.param(
            "from aiohttp.client_exceptions import ClientError",
            id="from_aiohttp_client_exceptions",
        ),
    ],
)
def test_flagged(
    linter: UnittestLinter,
    http_library_checker: HassEnforceHttpLibraryChecker,
    code: str,
) -> None:
    """Test imports that should be flagged."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    walk_checker(linter, http_library_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "hass-integration-raw-http-client"


@pytest.mark.parametrize(
    "code",
    [
        pytest.param("from aiohttp import web", id="aiohttp_web_import"),
        pytest.param("import aiohttp.web", id="aiohttp_web_module"),
        pytest.param("from aiohttp.web import Request", id="aiohttp_web_from"),
        pytest.param("import homeassistant.helpers.aiohttp_client", id="helper"),
        pytest.param("from . import requests", id="relative_import"),
        pytest.param("import my_device_library", id="library"),
    ],
)
def test_not_flagged(
    linter: UnittestLinter,
    http_library_checker: HassEnforceHttpLibraryChecker,
    code: str,
) -> None:
    """Test imports that should not be flagged."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")

    with assert_no_messages(linter):
        walk_checker(linter, http_library_checker, root_node)


def test_reports_library_name(
    linter: UnittestLinter,
    http_library_checker: HassEnforceHttpLibraryChecker,
) -> None:
    """Test that the offending library name is included in the message."""
    root_node = astroid.parse("import requests", "homeassistant.components.pylint_test")
    http_library_checker.visit_module(root_node)
    import_node = root_node.body[0]

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="hass-integration-raw-http-client",
            node=import_node,
            args=("requests",),
            line=1,
            col_offset=0,
            end_line=1,
            end_col_offset=15,
        ),
    ):
        http_library_checker.visit_import(import_node)


def test_grandfathered_domain_ignored(
    linter: UnittestLinter,
    http_library_checker: HassEnforceHttpLibraryChecker,
) -> None:
    """Test that grandfathered integrations are not flagged."""
    root_node = astroid.parse("import requests", "homeassistant.components.abode")

    with assert_no_messages(linter):
        walk_checker(linter, http_library_checker, root_node)


def test_non_integration_module_ignored(
    linter: UnittestLinter,
    http_library_checker: HassEnforceHttpLibraryChecker,
) -> None:
    """Test that non-integration modules are ignored."""
    root_node = astroid.parse("import requests", "tests.components.pylint_test")

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
