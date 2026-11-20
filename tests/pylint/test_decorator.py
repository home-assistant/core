"""Tests for pylint hass_enforce_type_hints plugin."""

import astroid
from pylint.checkers import BaseChecker
from pylint.interfaces import UNDEFINED
from pylint.testutils import MessageTest
from pylint.testutils.unittest_linter import UnittestLinter
import pytest

from . import assert_adds_messages, assert_no_messages, walk_checker


def test_good_callback(linter: UnittestLinter, decorator_checker: BaseChecker) -> None:
    """Test good `@callback` decorator."""
    code = """
    from homeassistant.core import callback

    @callback
    def setup(
        arg1, arg2
    ):
        pass
    """

    root_node = astroid.parse(code)

    with assert_no_messages(linter):
        walk_checker(linter, decorator_checker, root_node)


def test_bad_callback(linter: UnittestLinter, decorator_checker: BaseChecker) -> None:
    """Test bad `@callback` decorator."""
    code = """
    from homeassistant.core import callback

    @callback
    async def setup(
        arg1, arg2
    ):
        pass
    """

    root_node = astroid.parse(code)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-async-callback-decorator",
            line=5,
            node=root_node.body[1],
            args=None,
            confidence=UNDEFINED,
            col_offset=0,
            end_line=5,
            end_col_offset=15,
        ),
    ):
        walk_checker(linter, decorator_checker, root_node)


@pytest.mark.parametrize(
    ("keywords", "path"),
    [
        ('scope="function"', "tests.test_bootstrap"),
        ('scope="class"', "tests.test_bootstrap"),
        ('scope="module"', "tests.test_bootstrap"),
        ('scope="package"', "tests.test_bootstrap"),
        ('scope="session", autouse=True', "tests.test_bootstrap"),
        ('scope="function"', "tests.components.conftest"),
        ('scope="class"', "tests.components.conftest"),
        ('scope="module"', "tests.components.conftest"),
        ('scope="package"', "tests.components.conftest"),
        ('scope="session", autouse=True', "tests.components.conftest"),
        (
            'scope="session", autouse=find_spec("zeroconf") is not None',
            "tests.components.conftest",
        ),
        ('scope="function"', "tests.components.pylint_tests.conftest"),
        ('scope="class"', "tests.components.pylint_tests.conftest"),
        ('scope="module"', "tests.components.pylint_tests.conftest"),
        ('scope="package"', "tests.components.pylint_tests.conftest"),
        ('scope="function"', "tests.components.pylint_test"),
        ('scope="class"', "tests.components.pylint_test"),
        ('scope="module"', "tests.components.pylint_test"),
    ],
)
def test_good_fixture(
    linter: UnittestLinter, decorator_checker: BaseChecker, keywords: str, path: str
) -> None:
    """Test good `@pytest.fixture` decorator."""
    code = f"""
    import pytest

    @pytest.fixture
    def setup(
        arg1, arg2
    ):
        pass

    @pytest.fixture({keywords})
    def setup_session(
        arg1, arg2
    ):
        pass
    """

    root_node = astroid.parse(code, path)

    with assert_no_messages(linter):
        walk_checker(linter, decorator_checker, root_node)


@pytest.mark.parametrize(
    "path",
    [
        "tests.components.pylint_test",
        "tests.components.pylint_test.conftest",
        "tests.components.pylint_test.module",
    ],
)
def test_bad_fixture_session_scope(
    linter: UnittestLinter, decorator_checker: BaseChecker, path: str
) -> None:
    """Test bad `@pytest.fixture` decorator."""
    code = """
    import pytest

    @pytest.fixture
    def setup(
        arg1, arg2
    ):
        pass

    @pytest.fixture(scope="session")
    def setup_session(
        arg1, arg2
    ):
        pass
    """

    root_node = astroid.parse(code, path)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-pytest-fixture-decorator",
            line=10,
            node=root_node.body[2].decorators.nodes[0],
            args=("scope `session`", "use `package` or lower"),
            confidence=UNDEFINED,
            col_offset=1,
            end_line=10,
            end_col_offset=32,
        ),
    ):
        walk_checker(linter, decorator_checker, root_node)


@pytest.mark.parametrize(
    "path",
    [
        "tests.components.pylint_test",
        "tests.components.pylint_test.module",
    ],
)
def test_bad_fixture_package_scope(
    linter: UnittestLinter, decorator_checker: BaseChecker, path: str
) -> None:
    """Test bad `@pytest.fixture` decorator."""
    code = """
    import pytest

    @pytest.fixture
    def setup(
        arg1, arg2
    ):
        pass

    @pytest.fixture(scope="package")
    def setup_session(
        arg1, arg2
    ):
        pass
    """

    root_node = astroid.parse(code, path)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-pytest-fixture-decorator",
            line=10,
            node=root_node.body[2].decorators.nodes[0],
            args=("scope `package`", "use `module` or lower"),
            confidence=UNDEFINED,
            col_offset=1,
            end_line=10,
            end_col_offset=32,
        ),
    ):
        walk_checker(linter, decorator_checker, root_node)


@pytest.mark.parametrize(
    "keywords",
    [
        'scope="session"',
        'scope="session", autouse=False',
    ],
)
@pytest.mark.parametrize(
    "path",
    [
        "tests.test_bootstrap",
        "tests.components.conftest",
    ],
)
def test_bad_fixture_autouse(
    linter: UnittestLinter, decorator_checker: BaseChecker, keywords: str, path: str
) -> None:
    """Test bad `@pytest.fixture` decorator."""
    code = f"""
    import pytest

    @pytest.fixture
    def setup(
        arg1, arg2
    ):
        pass

    @pytest.fixture({keywords})
    def setup_session(
        arg1, arg2
    ):
        pass
    """

    root_node = astroid.parse(code, path)

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-pytest-fixture-decorator",
            line=10,
            node=root_node.body[2].decorators.nodes[0],
            args=("scope/autouse combination", "set `autouse=True` or reduce scope"),
            confidence=UNDEFINED,
            col_offset=1,
            end_line=10,
            end_col_offset=17 + len(keywords),
        ),
    ):
        walk_checker(linter, decorator_checker, root_node)


# Pre-load so astroid can resolve the base classes in parsed snippets
astroid.MANAGER.ast_from_module_name("homeassistant.helpers.update_coordinator")

_INTEGRATION_MODULE = "homeassistant.components.pylint_test.sensor"


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @callback
    def _handle_coordinator_update(self) -> None:
        pass
""",
            _INTEGRATION_MODULE,
            id="callback",
        ),
        pytest.param(
            """
from homeassistant import core
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @core.callback
    def _handle_coordinator_update(self) -> None:
        pass
""",
            _INTEGRATION_MODULE,
            id="core_callback",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    async def _handle_coordinator_update(self) -> None:
        pass
""",
            _INTEGRATION_MODULE,
            id="async_def",
        ),
        pytest.param(
            """
class MyClass:
    def _handle_coordinator_update(self) -> None:
        pass
""",
            _INTEGRATION_MODULE,
            id="not_a_coordinator_entity",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    def setup(self) -> None:
        def _handle_coordinator_update() -> None:
            pass
""",
            _INTEGRATION_MODULE,
            id="nested_function",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    def _handle_coordinator_update(self) -> None:
        pass
""",
            "homeassistant.helpers.pylint_test",
            id="outside_integration",
        ),
        pytest.param(
            """
from homeassistant.core import callback

class MyBaseEntity:
    @callback
    def __update(self) -> None:
        pass

class MyEntity(MyBaseEntity):
    def __update(self) -> None:
        pass
""",
            _INTEGRATION_MODULE,
            id="name_mangled",
        ),
        pytest.param(
            """
class MyBaseEntity:
    def _update(self) -> None:
        pass

class MyEntity(MyBaseEntity):
    def _update(self) -> None:
        pass
""",
            _INTEGRATION_MODULE,
            id="base_not_callback",
        ),
    ],
)
def test_good_callback_override(
    linter: UnittestLinter,
    decorator_checker: BaseChecker,
    code: str,
    module_name: str,
) -> None:
    """Test overrides of a @callback method that are not flagged."""
    root_node = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, decorator_checker, root_node)


@pytest.mark.parametrize(
    ("code", "method", "base"),
    [
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    def _handle_coordinator_update(self) -> None:
        pass
""",
            "_handle_coordinator_update",
            "BaseCoordinatorEntity",
            id="plain_override",
        ),
        pytest.param(
            """
from typing import override

from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyEntity(CoordinatorEntity):
    @override
    def _handle_coordinator_update(self) -> None:
        pass
""",
            "_handle_coordinator_update",
            "BaseCoordinatorEntity",
            id="override_only",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MyBaseEntity(CoordinatorEntity):
    pass

class MyEntity(MyBaseEntity):
    def _handle_coordinator_update(self) -> None:
        pass
""",
            "_handle_coordinator_update",
            "BaseCoordinatorEntity",
            id="indirect_subclass",
        ),
        pytest.param(
            """
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

class MyCoordinator(DataUpdateCoordinator[dict]):
    pass

class MyEntity(CoordinatorEntity[MyCoordinator]):
    def _handle_coordinator_update(self) -> None:
        pass
""",
            "_handle_coordinator_update",
            "BaseCoordinatorEntity",
            id="subscript_base",
        ),
        pytest.param(
            """
from homeassistant.helpers.entity import Entity

class MyEntity(Entity):
    def _async_write_ha_state(self) -> None:
        pass
""",
            "_async_write_ha_state",
            "Entity",
            id="async_write_ha_state",
        ),
        pytest.param(
            """
from homeassistant.components.weather import CoordinatorWeatherEntity

class MyWeather(CoordinatorWeatherEntity):
    def _async_forecast_daily(self) -> None:
        pass
""",
            "_async_forecast_daily",
            "CoordinatorWeatherEntity",
            id="weather_forecast",
        ),
        pytest.param(
            """
from homeassistant.core import callback

class MyBaseEntity:
    @callback
    def _update(self) -> None:
        pass

class MyEntity(MyBaseEntity):
    def _update(self) -> None:
        pass
""",
            "_update",
            "MyBaseEntity",
            id="integration_base_class",
        ),
        pytest.param(
            """
from homeassistant.core import callback

class MyBaseEntity:
    @callback
    def _update(self) -> None:
        pass

class MyMiddleEntity(MyBaseEntity):
    async def _update(self) -> None:
        pass

class MyEntity(MyMiddleEntity):
    def _update(self) -> None:
        pass
""",
            "_update",
            "MyBaseEntity",
            id="intermediate_without_callback",
        ),
        pytest.param(
            """
from homeassistant.core import callback

class MyBaseFlow:
    @staticmethod
    @callback
    def async_get_options_flow() -> None:
        pass

class MyFlow(MyBaseFlow):
    @staticmethod
    def async_get_options_flow() -> None:
        pass
""",
            "async_get_options_flow",
            "MyBaseFlow",
            id="staticmethod",
        ),
    ],
)
def test_bad_callback_override(
    linter: UnittestLinter,
    decorator_checker: BaseChecker,
    code: str,
    method: str,
    base: str,
) -> None:
    """Test overrides of a @callback method without @callback."""
    root_node = astroid.parse(code, _INTEGRATION_MODULE)
    func_node = root_node.body[-1].body[0]

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-callback-override-missing-decorator",
            line=func_node.position.lineno,
            node=func_node,
            args=(method, base),
            confidence=UNDEFINED,
            col_offset=func_node.col_offset,
            end_line=func_node.position.end_lineno,
            end_col_offset=func_node.position.end_col_offset,
        ),
    ):
        walk_checker(linter, decorator_checker, root_node)
