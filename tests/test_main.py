"""Test methods in __main__."""
from unittest.mock import patch, PropertyMock

from homeassistant import __main__ as main


@patch('sys.exit')
def test_validate_python(mock_exit):
    """Test validate Python version method."""
    with patch('sys.version_info',
               new_callable=PropertyMock(return_value=(2, 7, 8))):
        main.validate_python()
        assert mock_exit.called is True

    mock_exit.reset_mock()

    with patch('sys.version_info',
               new_callable=PropertyMock(return_value=(3, 2, 0))):
        main.validate_python()
        assert mock_exit.called is True

    mock_exit.reset_mock()

    with patch('sys.version_info',
               new_callable=PropertyMock(return_value=(3, 4, 2))):
        main.validate_python()
        assert mock_exit.called is True

    mock_exit.reset_mock()

    with patch('sys.version_info',
               new_callable=PropertyMock(return_value=(3, 5, 2))):
        main.validate_python()
        assert mock_exit.called is True

    mock_exit.reset_mock()

    with patch('sys.version_info',
               new_callable=PropertyMock(return_value=(3, 5, 3))):
        main.validate_python()
        assert mock_exit.called is False
