"""Tests for the snapshot enable entities checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.tests.snapshot_enable_entities import (
    SnapshotEnableEntitiesChecker,
)
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker

MODULE_NAME = "tests.components.test_integration.test_sensor"


@pytest.fixture(name="snapshot_enable_entities_checker")
def snapshot_enable_entities_checker_fixture(
    linter: UnittestLinter,
) -> SnapshotEnableEntitiesChecker:
    """Fixture to provide a snapshot enable entities checker."""
    return SnapshotEnableEntitiesChecker(linter)


def _expected_messages(root_node: nodes.Module) -> list[MessageTest]:
    """Build the expected messages for every ``async_update_entity`` call."""
    return [
        MessageTest(
            msg_id="home-assistant-tests-snapshot-enable-entities",
            node=call,
            line=call.lineno,
            col_offset=call.col_offset,
            end_line=call.end_lineno,
            end_col_offset=call.end_col_offset,
        )
        for call in root_node.nodes_of_class(nodes.Call)
        if isinstance(call.func, nodes.Attribute)
        and call.func.attrname == "async_update_entity"
    ]


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
async def test_all_entities(hass, entity_registry, snapshot, entry) -> None:
    await setup_integration(hass, entry)
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        entity_registry.async_update_entity(
            entity_entry.entity_id, disabled_by=None
        )
    await hass.config_entries.async_reload(entry.entry_id)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
""",
            id="loop_over_entries",
        ),
        pytest.param(
            """
async def test_all_entities(hass, entity_registry, snapshot, entry) -> None:
    await setup_integration(hass, entry)
    entity_registry.async_update_entity("sensor.one", disabled_by=None)
    entity_registry.async_update_entity("sensor.two", disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
""",
            id="multiple_calls",
        ),
        pytest.param(
            """
class TestSensor:
    async def test_all_entities(
        self, hass, entity_registry, snapshot, entry
    ) -> None:
        entity_registry.async_update_entity("sensor.one", disabled_by=None)
        await common.snapshot_platform(
            hass, entity_registry, snapshot, entry.entry_id
        )
""",
            id="method_and_attribute_access",
        ),
        pytest.param(
            """
def test_all_entities(hass, entity_registry, snapshot, entry) -> None:
    def _enable() -> None:
        entity_registry.async_update_entity("sensor.one", disabled_by=None)

    _enable()
    snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
""",
            id="nested_helper",
        ),
    ],
)
def test_manual_enable_flagged(
    linter: UnittestLinter,
    snapshot_enable_entities_checker: SnapshotEnableEntitiesChecker,
    code: str,
) -> None:
    """Enabling entities by hand in a snapshot_platform test is flagged."""
    root_node = astroid.parse(code, MODULE_NAME)

    with assert_adds_messages(linter, *_expected_messages(root_node)):
        walk_checker(linter, snapshot_enable_entities_checker, root_node)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(hass, entity_registry, snapshot, entry) -> None:
    await setup_integration(hass, entry)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
""",
            MODULE_NAME,
            id="uses_fixture",
        ),
        pytest.param(
            """
async def test_enable_entity(hass, entity_registry, entry) -> None:
    await setup_integration(hass, entry)
    entity_registry.async_update_entity("sensor.one", disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    assert hass.states.get("sensor.one")
""",
            MODULE_NAME,
            id="no_snapshot_platform",
        ),
        pytest.param(
            """
async def test_disable_entity(hass, entity_registry, snapshot, entry) -> None:
    entity_registry.async_update_entity(
        "sensor.one", disabled_by=er.RegistryEntryDisabler.USER
    )
    entity_registry.async_update_entity("sensor.two", name="Two")
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
""",
            MODULE_NAME,
            id="other_updates",
        ),
        pytest.param(
            """
async def test_enable(hass, entity_registry, entry) -> None:
    entity_registry.async_update_entity("sensor.one", disabled_by=None)


async def test_snapshot(hass, entity_registry, snapshot, entry) -> None:
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
""",
            MODULE_NAME,
            id="different_tests",
        ),
        pytest.param(
            """
async def enable_and_snapshot(hass, entity_registry, snapshot, entry) -> None:
    entity_registry.async_update_entity("sensor.one", disabled_by=None)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
""",
            MODULE_NAME,
            id="not_a_test_function",
        ),
        pytest.param(
            """
async def test_all_entities(hass, entity_registry, snapshot, entry) -> None:
    entity_registry.async_update_entity("sensor.one", disabled_by=None)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
""",
            "homeassistant.components.test_integration.sensor",
            id="not_a_test_module",
        ),
    ],
)
def test_not_flagged(
    linter: UnittestLinter,
    snapshot_enable_entities_checker: SnapshotEnableEntitiesChecker,
    code: str,
    module_name: str,
) -> None:
    """Valid patterns are not flagged."""
    root_node = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, snapshot_enable_entities_checker, root_node)
