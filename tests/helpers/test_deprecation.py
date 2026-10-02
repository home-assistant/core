"""Test deprecation helpers."""

from enum import StrEnum
import logging
import sys
from typing import Any
from unittest.mock import MagicMock, Mock, patch

from propcache.api import cached_property
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.deprecation import (
    DeprecatedAlias,
    DeprecatedConstant,
    DeprecatedConstantEnum,
    DeprecatedEntityAlias,
    EnumWithDeprecatedMembers,
    check_if_deprecated_constant,
    deprecated_class,
    deprecated_function,
    deprecated_hass_argument,
    deprecated_substitute,
    dir_with_deprecated_constants,
    get_deprecated,
    migrate_deprecated_entity_members,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.frame import MissingIntegrationFrame, ReportBehavior

from tests.common import MockModule, extract_stack_to_frame, mock_integration


class MockBaseClassDeprecatedProperty:
    """Mock base class for deprecated testing."""

    @property
    @deprecated_substitute("old_property")
    def new_property(self):
        """Test property to fetch."""
        return "default_new"


@patch("logging.getLogger")
def test_deprecated_substitute_old_class(mock_get_logger) -> None:
    """Test deprecated class object."""

    class MockDeprecatedClass(MockBaseClassDeprecatedProperty):
        """Mock deprecated class object."""

        @property
        def old_property(self):
            """Test property to fetch."""
            return "old"

    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger

    mock_object = MockDeprecatedClass()
    assert mock_object.new_property == "old"
    assert mock_logger.warning.called
    assert len(mock_logger.warning.mock_calls) == 1


@patch("logging.getLogger")
def test_deprecated_substitute_default_class(mock_get_logger) -> None:
    """Test deprecated class object."""

    class MockDefaultClass(MockBaseClassDeprecatedProperty):
        """Mock updated class object."""

    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger

    mock_object = MockDefaultClass()
    assert mock_object.new_property == "default_new"
    assert not mock_logger.warning.called


@patch("logging.getLogger")
def test_deprecated_substitute_new_class(mock_get_logger) -> None:
    """Test deprecated class object."""

    class MockUpdatedClass(MockBaseClassDeprecatedProperty):
        """Mock updated class object."""

        @property
        def new_property(self):
            """Test property to fetch."""
            return "new"

    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger

    mock_object = MockUpdatedClass()
    assert mock_object.new_property == "new"
    assert not mock_logger.warning.called


@patch("logging.getLogger")
def test_config_get_deprecated_old(mock_get_logger) -> None:
    """Test deprecated config."""
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger

    config = {"old_name": True}
    assert get_deprecated(config, "new_name", "old_name") is True
    assert mock_logger.warning.called
    assert len(mock_logger.warning.mock_calls) == 1


@patch("logging.getLogger")
def test_config_get_deprecated_new(mock_get_logger) -> None:
    """Test deprecated config."""
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger

    config = {"new_name": True}
    assert get_deprecated(config, "new_name", "old_name") is True
    assert not mock_logger.warning.called


@deprecated_class("homeassistant.blah.NewClass")
class MockDeprecatedClass:
    """Mock class for deprecated testing."""


class MockDeprecatedSubClass(MockDeprecatedClass):
    """Mock subclass for deprecated testing."""


@patch("logging.getLogger")
def test_deprecated_class(mock_get_logger) -> None:
    """Test deprecated class."""
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger

    MockDeprecatedClass()
    assert mock_logger.warning.called
    assert len(mock_logger.warning.mock_calls) == 1

    MockDeprecatedSubClass()
    assert len(mock_logger.warning.mock_calls) == 2


@pytest.mark.parametrize(
    ("breaks_in_ha_version", "extra_msg"),
    [
        (None, ""),
        ("2099.1", " It will be removed in HA Core 2099.1."),
    ],
)
def test_deprecated_function(
    caplog: pytest.LogCaptureFixture,
    breaks_in_ha_version: str | None,
    extra_msg: str,
) -> None:
    """Test deprecated_function decorator.

    This tests the behavior when the calling integration is not known.
    """

    @deprecated_function("new_function", breaks_in_ha_version=breaks_in_ha_version)
    def mock_deprecated_function():
        pass

    mock_deprecated_function()
    assert (
        "The deprecated function mock_deprecated_function was called."
        f"{extra_msg}"
        " Use new_function instead"
    ) in caplog.text


@pytest.mark.parametrize(
    ("breaks_in_ha_version", "extra_msg"),
    [
        (None, ""),
        ("2099.1", " It will be removed in HA Core 2099.1."),
    ],
)
def test_deprecated_function_called_from_built_in_integration(
    caplog: pytest.LogCaptureFixture,
    breaks_in_ha_version: str | None,
    extra_msg: str,
) -> None:
    """Test deprecated_function decorator.

    This tests the behavior when the calling integration is built-in.
    """

    @deprecated_function("new_function", breaks_in_ha_version=breaks_in_ha_version)
    def mock_deprecated_function():
        pass

    with (
        patch(
            "homeassistant.helpers.frame.linecache.getline",
            return_value="await session.close()",
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=extract_stack_to_frame(
                [
                    Mock(
                        filename="/home/paulus/homeassistant/core.py",
                        lineno="23",
                        line="do_something()",
                    ),
                    Mock(
                        filename="/home/paulus/homeassistant/components/hue/light.py",
                        lineno="23",
                        line="await session.close()",
                    ),
                    Mock(
                        filename="/home/paulus/aiohue/lights.py",
                        lineno="2",
                        line="something()",
                    ),
                ]
            ),
        ),
    ):
        mock_deprecated_function()
    assert (
        "The deprecated function mock_deprecated_function was called from hue."
        f"{extra_msg}"
        " Use new_function instead"
    ) in caplog.text


@pytest.mark.parametrize(
    ("breaks_in_ha_version", "extra_msg"),
    [
        (None, ""),
        ("2099.1", " It will be removed in HA Core 2099.1."),
    ],
)
def test_deprecated_function_called_from_custom_integration(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    breaks_in_ha_version: str | None,
    extra_msg: str,
) -> None:
    """Test deprecated_function decorator.

    This tests the behavior when the calling integration is custom.
    """

    mock_integration(hass, MockModule("hue"), built_in=False)

    @deprecated_function("new_function", breaks_in_ha_version=breaks_in_ha_version)
    def mock_deprecated_function():
        pass

    with (
        patch(
            "homeassistant.helpers.frame.linecache.getline",
            return_value="await session.close()",
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=extract_stack_to_frame(
                [
                    Mock(
                        filename="/home/paulus/homeassistant/core.py",
                        lineno="23",
                        line="do_something()",
                    ),
                    Mock(
                        filename="/home/paulus/config/custom_components/hue/light.py",
                        lineno="23",
                        line="await session.close()",
                    ),
                    Mock(
                        filename="/home/paulus/aiohue/lights.py",
                        lineno="2",
                        line="something()",
                    ),
                ]
            ),
        ),
    ):
        mock_deprecated_function()
    assert (
        "The deprecated function mock_deprecated_function was called from hue."
        f"{extra_msg}"
        " Use new_function instead, please report it to the author of the "
        "'hue' custom integration"
    ) in caplog.text


class TestDeprecatedConstantEnum(StrEnum):
    """Test deprecated constant enum."""

    __test__ = False  # prevent test collection of class by pytest

    TEST = "value"


def _get_value(
    obj: DeprecatedConstant
    | DeprecatedConstantEnum
    | DeprecatedAlias
    | tuple[Any, ...],
) -> Any:
    if isinstance(obj, DeprecatedConstant):
        return obj.value

    if isinstance(obj, DeprecatedConstantEnum):
        return obj.enum

    if isinstance(obj, DeprecatedAlias):
        return obj.value

    if len(obj) == 2:
        return obj[0].value

    return obj[0]


@pytest.mark.parametrize(
    ("deprecated_constant", "extra_msg", "description"),
    [
        (
            DeprecatedConstant("value", "NEW_CONSTANT", None),
            ". Use NEW_CONSTANT instead",
            "constant",
        ),
        (
            DeprecatedConstant(1, "NEW_CONSTANT", "2099.1"),
            ". It will be removed in HA Core 2099.1. Use NEW_CONSTANT instead",
            "constant",
        ),
        (
            DeprecatedConstantEnum(TestDeprecatedConstantEnum.TEST, None),
            ". Use TestDeprecatedConstantEnum.TEST instead",
            "constant",
        ),
        (
            DeprecatedConstantEnum(TestDeprecatedConstantEnum.TEST, "2099.1"),
            ". It will be removed in HA Core 2099.1."
            " Use TestDeprecatedConstantEnum.TEST instead",
            "constant",
        ),
        (
            DeprecatedAlias(1, "new_alias", None),
            ". Use new_alias instead",
            "alias",
        ),
        (
            DeprecatedAlias(1, "new_alias", "2099.1"),
            ". It will be removed in HA Core 2099.1. Use new_alias instead",
            "alias",
        ),
    ],
)
@pytest.mark.parametrize(
    ("module_name", "extra_extra_msg"),
    [
        ("homeassistant.components.hue.light", ""),  # builtin integration
        (
            "config.custom_components.hue.light",
            ", please report it to the author of the 'hue' custom integration",
        ),  # custom component integration
    ],
)
def test_check_if_deprecated_constant(
    caplog: pytest.LogCaptureFixture,
    deprecated_constant: DeprecatedConstant
    | DeprecatedConstantEnum
    | DeprecatedAlias
    | tuple,
    extra_msg: str,
    module_name: str,
    extra_extra_msg: str,
    description: str,
) -> None:
    """Test check_if_deprecated_constant."""
    module_globals = {
        "__name__": module_name,
        "_DEPRECATED_TEST_CONSTANT": deprecated_constant,
    }
    filename = f"/home/paulus/{module_name.replace('.', '/')}.py"

    # mock sys.modules for homeassistant/helpers/frame.py#get_integration_frame
    with (
        patch.dict(sys.modules, {module_name: Mock(__file__=filename)}),
        patch(
            "homeassistant.helpers.frame.linecache.getline",
            return_value="await session.close()",
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=extract_stack_to_frame(
                [
                    Mock(
                        filename="/home/paulus/homeassistant/core.py",
                        lineno="23",
                        line="do_something()",
                    ),
                    Mock(
                        filename=filename,
                        lineno="23",
                        line="await session.close()",
                    ),
                    Mock(
                        filename="/home/paulus/aiohue/lights.py",
                        lineno="2",
                        line="something()",
                    ),
                ]
            ),
        ),
    ):
        value = check_if_deprecated_constant("TEST_CONSTANT", module_globals)
        assert value == _get_value(deprecated_constant)

    assert (
        module_name,
        logging.WARNING,
        f"The deprecated {description} TEST_CONSTANT"
        f" was used from hue{extra_msg}{extra_extra_msg}",
    ) in caplog.record_tuples


@pytest.mark.parametrize(
    ("deprecated_constant", "extra_msg", "description"),
    [
        (
            DeprecatedConstant("value", "NEW_CONSTANT", None),
            ". Use NEW_CONSTANT instead",
            "constant",
        ),
        (
            DeprecatedConstant(1, "NEW_CONSTANT", "2099.1"),
            " which will be removed in HA Core 2099.1. Use NEW_CONSTANT instead",
            "constant",
        ),
        (
            DeprecatedConstantEnum(TestDeprecatedConstantEnum.TEST, None),
            ". Use TestDeprecatedConstantEnum.TEST instead",
            "constant",
        ),
        (
            DeprecatedConstantEnum(TestDeprecatedConstantEnum.TEST, "2099.1"),
            " which will be removed in HA Core 2099.1."
            " Use TestDeprecatedConstantEnum.TEST instead",
            "constant",
        ),
        (
            DeprecatedAlias(1, "new_alias", None),
            ". Use new_alias instead",
            "alias",
        ),
        (
            DeprecatedAlias(1, "new_alias", "2099.1"),
            " which will be removed in HA Core 2099.1. Use new_alias instead",
            "alias",
        ),
    ],
)
@pytest.mark.parametrize(
    ("module_name"),
    [
        "homeassistant.components.hue.light",  # builtin integration
        "config.custom_components.hue.light",  # custom component integration
    ],
)
def test_check_if_deprecated_constant_integration_not_found(
    caplog: pytest.LogCaptureFixture,
    deprecated_constant: DeprecatedConstant
    | DeprecatedConstantEnum
    | DeprecatedAlias
    | tuple,
    extra_msg: str,
    module_name: str,
    description: str,
) -> None:
    """Test check_if_deprecated_constant."""
    module_globals = {
        "__name__": module_name,
        "_DEPRECATED_TEST_CONSTANT": deprecated_constant,
    }

    with patch(
        "homeassistant.helpers.frame.get_current_frame",
        side_effect=MissingIntegrationFrame,
    ):
        value = check_if_deprecated_constant("TEST_CONSTANT", module_globals)
        assert value == _get_value(deprecated_constant)

    assert (
        module_name,
        logging.WARNING,
        f"TEST_CONSTANT is a deprecated {description}{extra_msg}",
    ) not in caplog.record_tuples


def test_test_check_if_deprecated_constant_invalid(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test check_if_deprecated_constant error handling.

    Test check_if_deprecated_constant raises an attribute error and creates a log entry
    on an invalid deprecation type.
    """
    module_name = "homeassistant.components.hue.light"
    module_globals = {"__name__": module_name, "_DEPRECATED_TEST_CONSTANT": 1}
    name = "TEST_CONSTANT"

    excepted_msg = (
        f"Value of _DEPRECATED_{name} is an instance of <class 'int'> but an instance "
        "of DeprecatedAlias, DeferredDeprecatedAlias, DeprecatedConstant or "
        "DeprecatedConstantEnum is required"
    )

    with pytest.raises(AttributeError, match=excepted_msg):
        check_if_deprecated_constant(name, module_globals)

    assert (module_name, logging.DEBUG, excepted_msg) in caplog.record_tuples


@pytest.mark.parametrize(
    ("module_globals", "expected"),
    [
        ({"CONSTANT": 1}, ["CONSTANT"]),
        ({"_DEPRECATED_CONSTANT": 1}, ["_DEPRECATED_CONSTANT", "CONSTANT"]),
        (
            {"_DEPRECATED_CONSTANT": 1, "SOMETHING": 2},
            ["_DEPRECATED_CONSTANT", "SOMETHING", "CONSTANT"],
        ),
    ],
)
def test_dir_with_deprecated_constants(
    module_globals: dict[str, Any], expected: list[str]
) -> None:
    """Test dir() with deprecated constants."""
    assert dir_with_deprecated_constants([*module_globals.keys()]) == expected


@pytest.mark.parametrize(
    ("module_name", "extra_extra_msg"),
    [
        ("homeassistant.components.hue.light", ""),  # builtin integration
        (
            "config.custom_components.hue.light",
            ", please report it to the author of the 'hue' custom integration",
        ),  # custom component integration
    ],
)
def test_enum_with_deprecated_members(
    caplog: pytest.LogCaptureFixture,
    module_name: str,
    extra_extra_msg: str,
) -> None:
    """Test EnumWithDeprecatedMembers."""
    filename = f"/home/paulus/{module_name.replace('.', '/')}.py"

    class TestEnum(
        StrEnum,
        metaclass=EnumWithDeprecatedMembers,
        deprecated={
            "CATS": ("TestEnum.CATS_PER_CM", "2025.11.0"),
            "DOGS": ("TestEnum.DOGS_PER_CM", None),
        },
    ):
        """Zoo units."""

        CATS_PER_CM = "cats/cm"
        DOGS_PER_CM = "dogs/cm"
        CATS = "cats/cm"
        DOGS = "dogs/cm"

    # mock sys.modules for homeassistant/helpers/frame.py#get_integration_frame
    with (
        patch.dict(sys.modules, {module_name: Mock(__file__=filename)}),
        patch(
            "homeassistant.helpers.frame.linecache.getline",
            return_value="await session.close()",
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=extract_stack_to_frame(
                [
                    Mock(
                        filename="/home/paulus/homeassistant/core.py",
                        lineno="23",
                        line="do_something()",
                    ),
                    Mock(
                        filename=filename,
                        lineno="23",
                        line="await session.close()",
                    ),
                    Mock(
                        filename="/home/paulus/aiohue/lights.py",
                        lineno="2",
                        line="something()",
                    ),
                ]
            ),
        ),
    ):
        TestEnum.CATS  # noqa: B018
        TestEnum.DOGS  # noqa: B018

    assert len(caplog.record_tuples) == 2
    assert (
        "tests.helpers.test_deprecation",
        logging.WARNING,
        (
            "The deprecated enum member TestEnum.CATS was used from hue. It "
            "will be removed in HA Core 2025.11.0. Use TestEnum.CATS_PER_CM instead"
            f"{extra_extra_msg}"
        ),
    ) in caplog.record_tuples
    assert (
        "tests.helpers.test_deprecation",
        logging.WARNING,
        (
            "The deprecated enum member TestEnum.DOGS was used from hue. Use "
            f"TestEnum.DOGS_PER_CM instead{extra_extra_msg}"
        ),
    ) in caplog.record_tuples


def test_enum_with_deprecated_members_integration_not_found(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test check_if_deprecated_constant."""

    class TestEnum(
        StrEnum,
        metaclass=EnumWithDeprecatedMembers,
        deprecated={
            "CATS": ("TestEnum.CATS_PER_CM", "2025.11.0"),
            "DOGS": ("TestEnum.DOGS_PER_CM", None),
        },
    ):
        """Zoo units."""

        CATS_PER_CM = "cats/cm"
        DOGS_PER_CM = "dogs/cm"
        CATS = "cats/cm"
        DOGS = "dogs/cm"

    with patch(
        "homeassistant.helpers.frame.get_current_frame",
        side_effect=MissingIntegrationFrame,
    ):
        TestEnum.CATS  # noqa: B018
        TestEnum.DOGS  # noqa: B018

    assert len(caplog.record_tuples) == 0


@pytest.mark.parametrize(
    ("positional_arguments", "keyword_arguments"),
    [
        # without kwargs
        ([], {}),
        (["first_arg"], {}),
        (["first_arg", "second_arg"], {}),
        # with single kwargs
        ([], {"first_kwarg": "first_value"}),
        (["first_arg"], {"first_kwarg": "first_value"}),
        (["first_arg", "second_arg"], {"first_kwarg": "first_value"}),
        # with double kwargs
        ([], {"first_kwarg": "first_value", "second_kwarg": "second_value"}),
        (["first_arg"], {"first_kwarg": "first_value", "second_kwarg": "second_value"}),
        (
            ["first_arg", "second_arg"],
            {"first_kwarg": "first_value", "second_kwarg": "second_value"},
        ),
    ],
)
@pytest.mark.parametrize(
    ("breaks_in_ha_version", "extra_msg"),
    [
        (None, ""),
        ("2099.1", " It will be removed in HA Core 2099.1."),
    ],
)
def test_deprecated_hass_argument(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    positional_arguments: list[str],
    keyword_arguments: dict[str, str],
    breaks_in_ha_version: str | None,
    extra_msg: str,
) -> None:
    """Test deprecated_hass_argument decorator."""

    calls = []

    @deprecated_hass_argument(breaks_in_ha_version=breaks_in_ha_version)
    def mock_deprecated_function(*args: str, **kwargs: str) -> None:
        calls.append((args, kwargs))

    mock_deprecated_function(*positional_arguments, **keyword_arguments)
    assert (
        "The deprecated argument hass was passed to mock_deprecated_function."
        f"{extra_msg}"
        " Use mock_deprecated_function without hass argument instead"
    ) not in caplog.text
    assert len(calls) == 1

    mock_deprecated_function(hass, *positional_arguments, **keyword_arguments)
    assert (
        "The deprecated argument hass was passed to mock_deprecated_function."
        f"{extra_msg}"
        " Use mock_deprecated_function without hass argument instead"
    ) in caplog.text
    assert len(calls) == 2

    caplog.clear()
    mock_deprecated_function(*positional_arguments, hass=hass, **keyword_arguments)
    assert (
        "The deprecated argument hass was passed to mock_deprecated_function."
        f"{extra_msg}"
        " Use mock_deprecated_function without hass argument instead"
    ) in caplog.text
    assert len(calls) == 3

    # Ensure that the two calls are the same, as the second call should have been
    # modified to remove the hass argument.
    assert calls[0] == calls[1]
    assert calls[0] == calls[2]


class MockAliasEntity(Entity, cached_properties={"native_value"}):
    """Entity base class which renamed value to native_value."""

    _attr_native_value: int | None = None

    value = DeprecatedEntityAlias[int | None]("native_value", "2099.1")
    _attr_value = DeprecatedEntityAlias[int | None]("_attr_native_value", "2099.1")

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Serve native_value from subclasses still providing value."""
        super().__init_subclass__(**kwargs)
        migrate_deprecated_entity_members(cls, MockAliasEntity)

    @cached_property
    def native_value(self) -> int | None:
        """Return the value."""
        return self._attr_native_value


def test_deprecated_entity_alias_class_attribute(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a deprecated _attr_ class attribute becomes the native storage."""

    class LegacyEntity(MockAliasEntity):
        _attr_value = 1

    entity = LegacyEntity()
    assert entity.native_value == 1
    assert (
        f"{__name__}::test_deprecated_entity_alias_class_attribute.<locals>."
        "LegacyEntity provides the deprecated _attr_value, this will stop working "
        "in Home Assistant 2099.1, use _attr_native_value instead"
    ) in caplog.text

    # Writes through either name invalidate the cached native property
    entity._attr_value = 2
    assert entity.native_value == 2
    entity._attr_native_value = 3
    assert entity.native_value == 3
    entity.value = 4
    assert entity.native_value == 4
    assert (
        "Detected code that writes the deprecated LegacyEntity._attr_value, "
        "use _attr_native_value instead"
    ) in caplog.text
    assert (
        "Detected code that writes the deprecated LegacyEntity.value, "
        "use native_value instead"
    ) in caplog.text


def test_deprecated_entity_alias_property(caplog: pytest.LogCaptureFixture) -> None:
    """Test a deprecated property override serves the native property."""

    class LegacyEntity(MockAliasEntity):
        reads = 0

        @property
        def value(self) -> int:
            self.reads += 1
            return self.reads

    class DelegatingEntity(LegacyEntity):
        @property
        def value(self) -> int:
            return super().value * 10

    # Not cached, the deprecated property may return a new value on every read
    assert [LegacyEntity().native_value for _ in range(2)] == [1, 1]
    entity = LegacyEntity()
    assert [entity.native_value for _ in range(2)] == [1, 2]
    assert DelegatingEntity().native_value == 10
    assert "LegacyEntity provides the deprecated value" in caplog.text
    assert "reads the deprecated" not in caplog.text


def test_deprecated_entity_alias_migrated(caplog: pytest.LogCaptureFixture) -> None:
    """Test a migrated subclass of a legacy class serves its native storage."""

    class LegacyEntity(MockAliasEntity):
        @property
        def value(self) -> int | None:
            return self._attr_value

    class MigratedEntity(LegacyEntity):
        _attr_native_value = 5

    class NativeEntity(MockAliasEntity):
        _attr_native_value = 6

    caplog.clear()
    assert MigratedEntity().native_value == 5
    assert NativeEntity().native_value == 6
    assert NativeEntity().value == 6
    assert "provides the deprecated" not in caplog.text
    assert _count_records(caplog, "reads the deprecated") == 2


class QuietAliasEntity(Entity, cached_properties={"native_value"}):
    """Entity base class not reporting core integrations."""

    _attr_native_value: int | None = None
    _attr_value = DeprecatedEntityAlias[int | None](
        "_attr_native_value",
        "2099.1",
        core_integration_behavior=ReportBehavior.IGNORE,
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Serve native_value from subclasses still providing value."""
        super().__init_subclass__(**kwargs)
        migrate_deprecated_entity_members(cls, QuietAliasEntity)

    @cached_property
    def native_value(self) -> int | None:
        """Return the value."""
        return self._attr_native_value


class StrictAliasEntity(Entity, cached_properties={"native_value"}):
    """Entity base class raising for core integrations."""

    _attr_native_value: int | None = None
    _attr_value = DeprecatedEntityAlias[int | None](
        "_attr_native_value",
        "2099.1",
        core_integration_behavior=ReportBehavior.ERROR,
    )

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Serve native_value from subclasses still providing value."""
        super().__init_subclass__(**kwargs)
        migrate_deprecated_entity_members(cls, StrictAliasEntity)

    @cached_property
    def native_value(self) -> int | None:
        """Return the value."""
        return self._attr_native_value


def test_deprecated_entity_alias_core_declaration_ignored(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test declarations in core integrations are not reported when ignored."""
    core = type(
        "CoreEntity",
        (QuietAliasEntity,),
        {"__module__": "homeassistant.components.hue.sensor", "_attr_value": 1},
    )
    custom = type(
        "CustomEntity",
        (QuietAliasEntity,),
        {"__module__": "custom_components.foo.sensor", "_attr_value": 2},
    )

    assert core().native_value == 1
    assert custom().native_value == 2
    assert "CoreEntity" not in caplog.text
    assert "custom_components.foo.sensor::CustomEntity provides" in caplog.text


def test_deprecated_entity_alias_core_declaration_error() -> None:
    """Test declarations in core integrations raise when set to error."""
    with pytest.raises(
        RuntimeError,
        match="homeassistant.components.hue.sensor::CoreEntity provides the "
        "deprecated _attr_value",
    ):
        type(
            "CoreEntity",
            (StrictAliasEntity,),
            {"__module__": "homeassistant.components.hue.sensor", "_attr_value": 1},
        )


@pytest.mark.usefixtures("hass", "mock_integration_frame")
def test_deprecated_entity_alias_core_usage_error() -> None:
    """Test usage from a core integration raises when set to error."""
    entity = StrictAliasEntity()

    with pytest.raises(
        RuntimeError,
        match="Detected that integration 'hue' writes the deprecated "
        "StrictAliasEntity._attr_value",
    ):
        entity._attr_value = 1


@pytest.mark.usefixtures("mock_integration_frame")
def test_deprecated_entity_alias_core_usage_error_without_frame_helper(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test usage before the frame helper is set up is logged, not raised."""
    entity = StrictAliasEntity()

    entity._attr_value = 1

    assert entity.native_value == 1
    assert (
        "Detected code that writes the deprecated StrictAliasEntity._attr_value"
    ) in caplog.text


def _count_records(caplog: pytest.LogCaptureFixture, text: str) -> int:
    """Return the number of logged records containing text."""
    return sum(text in record.getMessage() for record in caplog.records)
