"""Tests for the log and raise checker."""

import astroid
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.log_and_raise import LogAndRaiseChecker
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker

# Pre-load so astroid can resolve the exceptions in parsed snippets
astroid.MANAGER.ast_from_module_name("homeassistant.exceptions")
astroid.MANAGER.ast_from_module_name("homeassistant.helpers.update_coordinator")

_MODULE = "homeassistant.components.test_int.coordinator"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> LogAndRaiseChecker:
    """Fixture to provide a log and raise checker."""
    return LogAndRaiseChecker(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import UpdateFailed

async def update():
    try:
        await fetch()
    except OSError as err:
        _LOGGER.debug("Fetching failed: %s", err)
        raise UpdateFailed("Fetching failed") from err
""",
            _MODULE,
            id="debug_level",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import UpdateFailed

async def update():
    try:
        await fetch()
    except OSError as err:
        raise UpdateFailed("Fetching failed") from err
""",
            _MODULE,
            id="no_log",
        ),
        pytest.param(
            """
from homeassistant.exceptions import HomeAssistantError

class CannotConnect(HomeAssistantError):
    pass

async def connect():
    try:
        await fetch()
    except OSError as err:
        _LOGGER.error("Cannot connect: %s", err)
        raise CannotConnect from err
""",
            _MODULE,
            id="integration_exception",
        ),
        pytest.param(
            """
async def update():
    try:
        await fetch()
    except OSError as err:
        _LOGGER.error("Fetching failed: %s", err)
        raise ValueError from err
""",
            _MODULE,
            id="other_exception",
        ),
        pytest.param(
            """
async def update():
    try:
        await fetch()
    except OSError:
        _LOGGER.error("Fetching failed")
        raise
""",
            _MODULE,
            id="reraise",
        ),
        pytest.param(
            """
async def update():
    try:
        await fetch()
    except OSError as err:
        _LOGGER.error("Fetching failed: %s", err)
        raise UnknownError from err
""",
            _MODULE,
            id="uninferable_exception",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import UpdateFailed

async def update():
    try:
        await fetch()
    except OSError as err:
        if err.errno:
            _LOGGER.error("Fetching failed: %s", err)
        raise UpdateFailed("Fetching failed") from err
""",
            _MODULE,
            id="log_in_other_block",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import UpdateFailed

async def update():
    try:
        await fetch()
    except OSError as err:
        _LOGGER.error("Fetching failed: %s", err)
        raise UpdateFailed("Fetching failed") from err
""",
            "tests.components.test_int.test_coordinator",
            id="not_an_integration_module",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: LogAndRaiseChecker,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root)


@pytest.mark.parametrize(
    ("code", "exception"),
    [
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import UpdateFailed

async def update():
    try:
        await fetch()
    except OSError as err:
        _LOGGER.error("Fetching failed: %s", err)
        raise UpdateFailed("Fetching failed") from err
""",
            "UpdateFailed",
            id="update_failed",
        ),
        pytest.param(
            """
from homeassistant.exceptions import ConfigEntryNotReady

async def async_setup_entry(hass, entry):
    try:
        await connect()
    except OSError as err:
        _LOGGER.warning("Cannot connect")
        raise ConfigEntryNotReady from err
""",
            "ConfigEntryNotReady",
            id="config_entry_not_ready_class",
        ),
        pytest.param(
            """
from homeassistant import exceptions

async def async_setup_entry(hass, entry):
    if not await connect():
        _LOGGER.error("Cannot connect")
        raise exceptions.ConfigEntryNotReady("Cannot connect")
""",
            "ConfigEntryNotReady",
            id="outside_except",
        ),
        pytest.param(
            """
from homeassistant.exceptions import HomeAssistantError

class MyEntity:
    async def async_turn_on(self):
        try:
            await self.device.turn_on()
        except OSError as err:
            self._logger.exception("Turning on failed")
            self._attr_is_on = False
            raise HomeAssistantError("Turning on failed") from err
""",
            "HomeAssistantError",
            id="logger_attribute_not_directly_before",
        ),
    ],
)
def test_warning(
    linter: UnittestLinter,
    checker: LogAndRaiseChecker,
    code: str,
    exception: str,
) -> None:
    """Test cases that should trigger a warning."""
    root = astroid.parse(code, _MODULE)
    log_call = next(
        node
        for node in root.nodes_of_class(astroid.nodes.Expr)
        if isinstance(node.value, astroid.nodes.Call)
        and getattr(node.value.func, "attrname", None)
        in {"error", "exception", "warning"}
    )

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-log-and-raise",
            node=log_call,
            args=(exception,),
            line=log_call.lineno,
            col_offset=log_call.col_offset,
            end_line=log_call.end_lineno,
            end_col_offset=log_call.end_col_offset,
        ),
    ):
        walk_checker(linter, checker, root)
