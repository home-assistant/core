"""Tests for the coordinator entity async_update checker."""

import astroid
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.coordinator_entity_async_update import (
    CoordinatorEntityAsyncUpdateChecker,
)
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker

# Pre-load so astroid can resolve CoordinatorEntity in parsed snippets
astroid.MANAGER.ast_from_module_name("homeassistant.helpers.update_coordinator")

_MODULE = "homeassistant.components.test_int.sensor"


@pytest.fixture(name="checker")
def checker_fixture(linter: UnittestLinter) -> CoordinatorEntityAsyncUpdateChecker:
    """Fixture to provide a coordinator entity async_update checker."""
    return CoordinatorEntityAsyncUpdateChecker(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    async def async_update(self) -> None:
        await super().async_update()
        await self.firmware_coordinator.async_request_refresh()
""",
            _MODULE,
            id="super_async_update",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity, UpdateEntity):
    async def async_update(self) -> None:
        await CoordinatorEntity.async_update(self)
        await super().async_update()
""",
            _MODULE,
            id="explicit_parent_async_update",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    async def async_update(self) -> None:
        \"\"\"Updates are pushed by the device.\"\"\"
""",
            _MODULE,
            id="docstring_only",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    async def async_update(self) -> None:
        pass
""",
            _MODULE,
            id="pass_only",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def should_poll(self) -> bool:
        return True

    async def async_update(self) -> None:
        self._attr_latest_version = await self.client.latest_version()
""",
            _MODULE,
            id="should_poll_property",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    _attr_should_poll = True

    async def async_update(self) -> None:
        self._attr_native_value = await self.device.get_offset()
""",
            _MODULE,
            id="attr_should_poll",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyBaseEntity(CoordinatorEntity):
    _attr_should_poll = True

class MyEntity(MyBaseEntity):
    async def async_update(self) -> None:
        self._attr_native_value = await self.device.get_offset()
""",
            _MODULE,
            id="inherited_should_poll",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    async def async_update(self) -> None:
        self._attr_native_value = await self.device.get_value()
""",
            _MODULE,
            id="not_a_coordinator_entity",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    async def async_update(self) -> None:
        self._attr_native_value = await self.device.get_value()
""",
            "tests.components.test_int.test_sensor",
            id="not_an_integration_module",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    checker: CoordinatorEntityAsyncUpdateChecker,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, checker, root)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    async def async_update(self) -> None:
        self._attr_native_value = await self.device.get_value()
""",
            id="coordinator_entity",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import BaseCoordinatorEntity

class MyEntity(BaseCoordinatorEntity):
    async def async_update(self) -> None:
        await self._device.update()
""",
            id="base_coordinator_entity",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()
        await self.other_coordinator.async_request_refresh()
""",
            id="refresh_without_super",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    _attr_should_poll = False

    async def async_update(self) -> None:
        self._attr_native_value = await self.device.get_value()
""",
            id="attr_should_poll_false",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @property
    def should_poll(self) -> bool:
        return False

    async def async_update(self) -> None:
        self._attr_native_value = await self.device.get_value()
""",
            id="should_poll_property_false",
        ),
    ],
)
def test_warning(
    linter: UnittestLinter,
    checker: CoordinatorEntityAsyncUpdateChecker,
    code: str,
) -> None:
    """Test cases that should trigger a warning."""
    root = astroid.parse(code, _MODULE)
    async_update = root.body[-1].locals["async_update"][0]

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-coordinator-entity-async-update",
            node=async_update,
            line=async_update.position.lineno,
            col_offset=async_update.position.col_offset,
            end_line=async_update.position.end_lineno,
            end_col_offset=async_update.position.end_col_offset,
        ),
    ):
        walk_checker(linter, checker, root)
