"""Test deprecation helpers."""
from unittest.mock import MagicMock, patch

from homeassistant.helpers.deprecation import deprecated_substitute, get_deprecated


class MockBaseClass:
    """Mock base class for deprecated testing."""

    @property
    @deprecated_substitute("old_property")
    def new_property(self):
        """Test property to fetch."""
        raise NotImplementedError()


class MockDeprecatedClass(MockBaseClass):
    """Mock deprecated class object."""

    @property
    def old_property(self):
        """Test property to fetch."""
        return True


class MockUpdatedClass(MockBaseClass):
    """Mock updated class object."""

    @property
    def new_property(self):
        """Test property to fetch."""
        return True


@patch("logging.getLogger")
def test_deprecated_substitute_old_class(mock_get_logger):
    """Test deprecated class object."""
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger

    mock_object = MockDeprecatedClass()
    assert mock_object.new_property is True
    assert mock_object.new_property is True
    assert mock_logger.warning.called
    assert len(mock_logger.warning.mock_calls) == 1


@patch("logging.getLogger")
def test_deprecated_substitute_new_class(mock_get_logger):
    """Test deprecated class object."""
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger

    mock_object = MockUpdatedClass()
    assert mock_object.new_property is True
    assert mock_object.new_property is True
    assert not mock_logger.warning.called


@patch("logging.getLogger")
def test_config_get_deprecated_old(mock_get_logger):
    """Test deprecated class object."""
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger

    config = {"old_name": True}
    assert get_deprecated(config, "new_name", "old_name") is True
    assert mock_logger.warning.called
    assert len(mock_logger.warning.mock_calls) == 1


@patch("logging.getLogger")
def test_config_get_deprecated_new(mock_get_logger):
    """Test deprecated class object."""
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger

    config = {"new_name": True}
    assert get_deprecated(config, "new_name", "old_name") is True
    assert not mock_logger.warning.called
