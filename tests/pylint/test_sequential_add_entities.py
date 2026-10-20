"""Tests for the sequential add entities checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint_home_assistant.checkers.sequential_add_entities import (
    SequentialAddEntitiesChecker,
)
import pytest

from . import assert_no_messages, walk_checker

INTEGRATION_MODULE = "homeassistant.components.test_integration.sensor"


@pytest.fixture(name="add_entities_checker")
def add_entities_checker_fixture(
    linter: UnittestLinter,
) -> SequentialAddEntitiesChecker:
    """Fixture to provide a sequential add entities checker."""
    return SequentialAddEntitiesChecker(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SensorA(), SensorB()])
""",
            INTEGRATION_MODULE,
            id="single_call",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SensorA()])
    coordinator = entry.runtime_data
    async_add_entities([SensorB(coordinator)])
""",
            INTEGRATION_MODULE,
            id="separated_by_other_statement",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SensorA()])
    if entry.data["extra"]:
        async_add_entities([SensorB()])
""",
            INTEGRATION_MODULE,
            id="separated_by_control_flow",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    for subentry_id, subentry in entry.subentries.items():
        async_add_entities([SensorA(subentry)], config_subentry_id=subentry_id)
""",
            INTEGRATION_MODULE,
            id="subentry_loop",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SensorA()], config_subentry_id="subentry_1")
    async_add_entities([SensorB()], config_subentry_id="subentry_2")
""",
            INTEGRATION_MODULE,
            id="different_subentries",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SensorA()])
    async_add_entities([SensorB()], config_subentry_id="subentry_1")
""",
            INTEGRATION_MODULE,
            id="entry_and_subentry",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SensorA()])
    async_add_entities([SensorB()], update_before_add=True)
""",
            INTEGRATION_MODULE,
            id="different_update_before_add",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SensorA()], **kwargs)
    async_add_entities([SensorB()], **kwargs)
""",
            INTEGRATION_MODULE,
            id="unpacked_keywords",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    def add_entities():
        async_add_entities([SensorA()])

    add_entities()
    add_entities()
""",
            INTEGRATION_MODULE,
            id="local_helper_function",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SensorA()])
    async_add_entities([SensorB()])
""",
            "tests.components.test_integration.test_sensor",
            id="not_integration_module",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    add_entities_checker: SequentialAddEntitiesChecker,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, add_entities_checker, root_node)


@pytest.mark.parametrize(
    ("code", "expected_lines", "callback_name"),
    [
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SensorA()])
    async_add_entities([SensorB()])
""",
            [4],
            "async_add_entities",
            id="two_sequential",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SensorA()])
    async_add_entities([SensorB()])
    async_add_entities([SensorC()])
""",
            [4, 5],
            "async_add_entities",
            id="three_sequential",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SensorA()], config_subentry_id="subentry_1")
    async_add_entities([SensorB()], config_subentry_id="subentry_1")
""",
            [4],
            "async_add_entities",
            id="same_subentry",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    for subentry_id, subentry in entry.subentries.items():
        async_add_entities([SensorA(subentry)], config_subentry_id=subentry_id)
        async_add_entities([SensorB(subentry)], config_subentry_id=subentry_id)
""",
            [5],
            "async_add_entities",
            id="same_subentry_in_loop",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    if entry.data["extra"]:
        async_add_entities([SensorA()])
        async_add_entities([SensorB()])
""",
            [5],
            "async_add_entities",
            id="inside_if_block",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    @callback
    def _async_add_new_devices(devices):
        async_add_entities([SensorA(device) for device in devices])
        async_add_entities([SensorB(device) for device in devices])
""",
            [6],
            "async_add_entities",
            id="nested_callback",
        ),
        pytest.param(
            """
def setup_platform(hass, config, add_entities, discovery_info=None):
    add_entities([SensorA()])
    add_entities([SensorB()])
""",
            [4],
            "add_entities",
            id="setup_platform",
        ),
    ],
)
def test_sequential_flagged(
    linter: UnittestLinter,
    add_entities_checker: SequentialAddEntitiesChecker,
    code: str,
    expected_lines: list[int],
    callback_name: str,
) -> None:
    """Test that sequential async_add_entities calls are flagged."""
    root_node = astroid.parse(code, INTEGRATION_MODULE)
    walk_checker(linter, add_entities_checker, root_node)

    messages = linter.release_messages()
    assert [message.line for message in messages] == expected_lines
    assert {message.msg_id for message in messages} == {
        "home-assistant-sequential-add-entities"
    }
    assert {message.args for message in messages} == {(callback_name,)}
