"""Tests for the home-assistant-raise-third-party-exception checker."""

import astroid
from pylint.checkers import BaseChecker
from pylint.testutils.unittest_linter import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
import pytest

from . import assert_no_messages


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
        raise ValueError("bad value")
        """,
            id="stdlib_exception",
        ),
        pytest.param(
            """
        raise RuntimeError
        """,
            id="stdlib_exception_no_call",
        ),
        pytest.param(
            """
        from homeassistant.exceptions import HomeAssistantError

        raise HomeAssistantError("nope")
        """,
            id="ha_exception",
        ),
        pytest.param(
            """
        from homeassistant.helpers.update_coordinator import UpdateFailed

        raise UpdateFailed("nope")
        """,
            id="ha_update_failed",
        ),
        pytest.param(
            """
        class MyError(Exception):
            pass

        raise MyError("local")
        """,
            id="locally_defined_exception",
        ),
        pytest.param(
            """
        from .errors import MyLocalError

        raise MyLocalError("local")
        """,
            id="relative_import",
        ),
        pytest.param(
            """
        import voluptuous as vol

        raise vol.Invalid("bad config")
        """,
            id="voluptuous_invalid_via_module",
        ),
        pytest.param(
            """
        from voluptuous import Invalid

        raise Invalid("bad config")
        """,
            id="voluptuous_invalid_via_from",
        ),
        pytest.param(
            """
        from aiohttp import web

        raise web.HTTPNotFound()
        """,
            id="aiohttp_web_via_attribute",
        ),
        pytest.param(
            """
        from aiohttp.web import HTTPNotFound

        raise HTTPNotFound()
        """,
            id="aiohttp_web_via_from",
        ),
        pytest.param(
            """
        from aiohttp.web_exceptions import HTTPMethodNotAllowed

        raise HTTPMethodNotAllowed("GET", ["POST"])
        """,
            id="aiohttp_web_exceptions_via_from",
        ),
        pytest.param(
            """
        import aiohttp

        raise aiohttp.web_exceptions.HTTPMethodNotAllowed("GET", ["POST"])
        """,
            id="aiohttp_web_exceptions_via_module",
        ),
        pytest.param(
            """
        try:
            pass
        except Exception:
            raise
        """,
            id="bare_reraise",
        ),
        pytest.param(
            """
        from hole.exceptions import HoleError

        try:
            pass
        except HoleError as err:
            raise
        """,
            id="bare_reraise_with_third_party_caught",
        ),
        pytest.param(
            """
        from hole.exceptions import HoleError
        from homeassistant.exceptions import HomeAssistantError

        try:
            pass
        except HoleError as err:
            raise HomeAssistantError("wrapped") from err
        """,
            id="wrap_third_party_in_ha_exception",
        ),
    ],
)
def test_raise_third_party_good(
    linter: UnittestLinter,
    raise_third_party_checker: BaseChecker,
    code: str,
) -> None:
    """Good test cases -- no message expected."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    walker = ASTWalker(linter)
    walker.add_checker(raise_third_party_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("code", "exception", "module"),
    [
        pytest.param(
            """
        from hole.exceptions import HoleError

        raise HoleError("oops")
        """,
            "HoleError",
            "hole.exceptions",
            id="from_import_then_raise",
        ),
        pytest.param(
            """
        from hole.exceptions import HoleError as _HoleError

        raise _HoleError("oops")
        """,
            "_HoleError",
            "hole.exceptions",
            id="from_import_aliased",
        ),
        pytest.param(
            """
        from hole.exceptions import HoleError

        raise HoleError
        """,
            "HoleError",
            "hole.exceptions",
            id="raise_class_without_call",
        ),
        pytest.param(
            """
        import numato_gpio as gpio

        raise gpio.NumatoGpioError("oops")
        """,
            "gpio.NumatoGpioError",
            "numato_gpio",
            id="module_import_then_attribute",
        ),
        pytest.param(
            """
        import aiohomekit

        raise aiohomekit.exceptions.MalformedPinError("oops")
        """,
            "aiohomekit.exceptions.MalformedPinError",
            "aiohomekit",
            id="module_import_deep_attribute",
        ),
        pytest.param(
            """
        import aiohttp

        raise aiohttp.ClientError("oops")
        """,
            "aiohttp.ClientError",
            "aiohttp",
            id="aiohttp_non_web_attribute",
        ),
        pytest.param(
            """
        from aiohttp import ClientError

        raise ClientError("oops")
        """,
            "ClientError",
            "aiohttp",
            id="aiohttp_non_web_from_import",
        ),
    ],
)
def test_raise_third_party_bad(
    linter: UnittestLinter,
    raise_third_party_checker: BaseChecker,
    code: str,
    exception: str,
    module: str,
) -> None:
    """Bad test cases -- one message expected."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    walker = ASTWalker(linter)
    walker.add_checker(raise_third_party_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-raise-third-party-exception"
    assert messages[0].args == (exception, module)


def test_raise_third_party_skipped_outside_integration(
    linter: UnittestLinter,
    raise_third_party_checker: BaseChecker,
) -> None:
    """Files outside ``homeassistant.components.*`` are not checked."""
    code = """
        from hole.exceptions import HoleError

        raise HoleError("oops")
        """
    root_node = astroid.parse(code, "homeassistant.helpers.something")
    walker = ASTWalker(linter)
    walker.add_checker(raise_third_party_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)
