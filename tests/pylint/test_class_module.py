"""Tests for pylint hass_enforce_class_module plugin."""

import astroid
from pylint.checkers import BaseChecker
from pylint.interfaces import UNDEFINED
from pylint.testutils import MessageTest
from pylint.testutils.unittest_linter import UnittestLinter
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
    class DataUpdateCoordinator:
        pass

    class TestCoordinator(DataUpdateCoordinator):
        pass
    """,
            id="simple",
        ),
        pytest.param(
            """
    class DataUpdateCoordinator:
        pass

    class TestCoordinator(DataUpdateCoordinator):
        pass

    class TestCoordinator2(TestCoordinator):
        pass
    """,
            id="nested",
        ),
    ],
)
@pytest.mark.parametrize(
    "path",
    [
        "homeassistant.components.pylint_test.coordinator",
        "homeassistant.components.pylint_test.coordinator.my_coordinator",
    ],
)
def test_enforce_class_module_good(
    linter: UnittestLinter,
    enforce_class_module_checker: BaseChecker,
    code: str,
    path: str,
) -> None:
    """Good test cases."""
    root_node = astroid.parse(code, path)

    with assert_no_messages(linter):
        walk_checker(linter, enforce_class_module_checker, root_node)


@pytest.mark.parametrize(
    "path",
    [
        "homeassistant.components.sensor",
        "homeassistant.components.sensor.entity",
        "homeassistant.components.pylint_test.sensor",
        "homeassistant.components.pylint_test.sensor.entity",
    ],
)
def test_enforce_class_platform_good(
    linter: UnittestLinter,
    enforce_class_module_checker: BaseChecker,
    path: str,
) -> None:
    """Good test cases."""
    code = """
    class SensorEntity:
        pass

    class CustomSensorEntity(SensorEntity):
        pass

    class CoordinatorEntity:
        pass

    class CustomCoordinatorSensorEntity(CoordinatorEntity, SensorEntity):
        pass
    """
    root_node = astroid.parse(code, path)

    with assert_no_messages(linter):
        walk_checker(linter, enforce_class_module_checker, root_node)


@pytest.mark.parametrize(
    "path",
    [
        "homeassistant.components.pylint_test",
        "homeassistant.components.pylint_test.my_coordinator",
        "homeassistant.components.pylint_test.coordinator_other",
        "homeassistant.components.pylint_test.sensor",
    ],
)
def test_enforce_class_module_bad_simple(
    linter: UnittestLinter,
    enforce_class_module_checker: BaseChecker,
    path: str,
) -> None:
    """Bad test case with coordinator extending directly."""
    root_node = astroid.parse(
        """
    class DataUpdateCoordinator:
        pass

    class TestCoordinator(DataUpdateCoordinator):
        pass

    class CoordinatorEntity:
        pass

    class CustomCoordinatorSensorEntity(CoordinatorEntity):
        pass
    """,
        path,
    )

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-enforce-class-module",
            line=5,
            node=root_node.body[1],
            args=("DataUpdateCoordinator", "coordinator"),
            confidence=UNDEFINED,
            col_offset=0,
            end_line=5,
            end_col_offset=21,
        ),
        MessageTest(
            msg_id="home-assistant-enforce-class-module",
            line=11,
            node=root_node.body[3],
            args=("CoordinatorEntity", "entity"),
            confidence=UNDEFINED,
            col_offset=0,
            end_line=11,
            end_col_offset=35,
        ),
    ):
        walk_checker(linter, enforce_class_module_checker, root_node)


@pytest.mark.parametrize(
    "path",
    [
        "homeassistant.components.pylint_test",
        "homeassistant.components.pylint_test.my_coordinator",
        "homeassistant.components.pylint_test.coordinator_other",
        "homeassistant.components.pylint_test.sensor",
    ],
)
def test_enforce_class_module_bad_nested(
    linter: UnittestLinter,
    enforce_class_module_checker: BaseChecker,
    path: str,
) -> None:
    """Bad test case with nested coordinators."""
    root_node = astroid.parse(
        """
    class DataUpdateCoordinator:
        pass

    class TestCoordinator(DataUpdateCoordinator):
        pass

    class NopeCoordinator(TestCoordinator):
        pass
    """,
        path,
    )

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-enforce-class-module",
            line=5,
            node=root_node.body[1],
            args=("DataUpdateCoordinator", "coordinator"),
            confidence=UNDEFINED,
            col_offset=0,
            end_line=5,
            end_col_offset=21,
        ),
        MessageTest(
            msg_id="home-assistant-enforce-class-module",
            line=8,
            node=root_node.body[2],
            args=("DataUpdateCoordinator", "coordinator"),
            confidence=UNDEFINED,
            col_offset=0,
            end_line=8,
            end_col_offset=21,
        ),
    ):
        walk_checker(linter, enforce_class_module_checker, root_node)


@pytest.mark.parametrize(
    "path",
    [
        "homeassistant.components.sensor",
        "homeassistant.components.sensor.entity",
        "homeassistant.components.pylint_test.entity",
    ],
)
def test_enforce_entity_good(
    linter: UnittestLinter,
    enforce_class_module_checker: BaseChecker,
    path: str,
) -> None:
    """Good test cases."""
    code = """
    class Entity:
        pass

    class CustomEntity(Entity):
        pass
    """
    root_node = astroid.parse(code, path)

    with assert_no_messages(linter):
        walk_checker(linter, enforce_class_module_checker, root_node)


@pytest.mark.parametrize(
    "path",
    [
        "homeassistant.components.pylint_test",
        "homeassistant.components.pylint_test.select",
        "homeassistant.components.pylint_test.select.entity",
    ],
)
def test_enforce_entity_bad(
    linter: UnittestLinter,
    enforce_class_module_checker: BaseChecker,
    path: str,
) -> None:
    """Good test cases."""
    code = """
    class Entity:
        pass

    class CustomEntity(Entity):
        pass
    """
    root_node = astroid.parse(code, path)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-enforce-class-module",
            line=5,
            node=root_node.body[1],
            args=("Entity", "entity"),
            confidence=UNDEFINED,
            col_offset=0,
            end_line=5,
            end_col_offset=18,
        ),
    ):
        walk_checker(linter, enforce_class_module_checker, root_node)


@pytest.mark.parametrize(
    ("base_class", "module"),
    [
        ("InfraredEmitterEntity", "infrared"),
        ("InfraredEmitterEntityDescription", "infrared"),
        ("InfraredReceiverEntity", "infrared"),
        ("InfraredReceiverEntityDescription", "infrared"),
        ("RadioFrequencyTransmitterEntity", "radio_frequency"),
        ("RadioFrequencyTransmitterEntityDescription", "radio_frequency"),
    ],
)
def test_enforce_platform_class_good(
    linter: UnittestLinter,
    enforce_class_module_checker: BaseChecker,
    base_class: str,
    module: str,
) -> None:
    """Good test cases for platform classes."""
    code = f"""
    class {base_class}:
        pass

    class Custom{base_class}({base_class}):
        pass
    """
    root_node = astroid.parse(code, f"homeassistant.components.pylint_test.{module}")

    with assert_no_messages(linter):
        walk_checker(linter, enforce_class_module_checker, root_node)


@pytest.mark.parametrize(
    ("base_class", "module"),
    [
        ("InfraredEmitterEntity", "infrared"),
        ("InfraredEmitterEntityDescription", "infrared"),
        ("InfraredReceiverEntity", "infrared"),
        ("InfraredReceiverEntityDescription", "infrared"),
        ("RadioFrequencyTransmitterEntity", "radio_frequency"),
        ("RadioFrequencyTransmitterEntityDescription", "radio_frequency"),
    ],
)
def test_enforce_platform_class_bad(
    linter: UnittestLinter,
    enforce_class_module_checker: BaseChecker,
    base_class: str,
    module: str,
) -> None:
    """Bad test cases for platform classes."""
    code = f"""
    class {base_class}:
        pass

    class Custom{base_class}({base_class}):
        pass
    """
    root_node = astroid.parse(code, "homeassistant.components.pylint_test.sensor")

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-enforce-class-module",
            line=5,
            node=root_node.body[1],
            args=(base_class, module),
            confidence=UNDEFINED,
            col_offset=0,
            end_line=5,
            end_col_offset=len(f"class Custom{base_class}"),
        ),
    ):
        walk_checker(linter, enforce_class_module_checker, root_node)
