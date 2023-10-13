"""Test deprecation helpers."""
from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.deprecation import (
    deprecated_class,
    deprecated_function,
    deprecated_substitute,
    get_deprecated,
)

from tests.common import MockModule, mock_integration


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


@patch("logging.getLogger")
def test_deprecated_class(mock_get_logger) -> None:
    """Test deprecated class."""
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger

    MockDeprecatedClass()
    assert mock_logger.warning.called
    assert len(mock_logger.warning.mock_calls) == 1


def test_deprecated_function(caplog: pytest.LogCaptureFixture) -> None:
    """Test deprecated_function decorator.

    This tests the behavior when the calling integration is not known.
    """

    @deprecated_function("new_function")
    def mock_deprecated_function():
        pass

    mock_deprecated_function()
    assert (
        "mock_deprecated_function is a deprecated function. Use new_function instead"
        in caplog.text
    )


def test_deprecated_function_called_from_built_in_integration(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test deprecated_function decorator.

    This tests the behavior when the calling integration is built-in.
    """

    @deprecated_function("new_function")
    def mock_deprecated_function():
        pass

    with patch(
        "homeassistant.helpers.frame.extract_stack",
        return_value=[
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
        ],
    ):
        mock_deprecated_function()
    assert (
        "mock_deprecated_function was called from hue, this is a deprecated function. "
        "Use new_function instead" in caplog.text
    )


def test_deprecated_function_called_from_custom_integration(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test deprecated_function decorator.

    This tests the behavior when the calling integration is custom.
    """

    mock_integration(hass, MockModule("hue"), built_in=False)

    @deprecated_function("new_function")
    def mock_deprecated_function():
        pass

    with patch(
        "homeassistant.helpers.frame.extract_stack",
        return_value=[
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
        ],
    ):
        mock_deprecated_function()
    assert (
        "mock_deprecated_function was called from hue, this is a deprecated function. "
        "Use new_function instead, please report it to the author of the 'hue' custom "
        "integration" in caplog.text
    )
