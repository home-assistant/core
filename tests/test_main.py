"""Test methods in __main__."""
from homeassistant import __main__ as main
from homeassistant.const import REQUIRED_PYTHON_VER

from tests.async_mock import PropertyMock, patch


@patch("sys.exit")
def test_validate_python(mock_exit):
    """Test validate Python version method."""
    with patch("sys.version_info", new_callable=PropertyMock(return_value=(2, 7, 8))):
        main.validate_python()
        assert mock_exit.called is True

    mock_exit.reset_mock()

    with patch("sys.version_info", new_callable=PropertyMock(return_value=(3, 2, 0))):
        main.validate_python()
        assert mock_exit.called is True

    mock_exit.reset_mock()

    with patch("sys.version_info", new_callable=PropertyMock(return_value=(3, 4, 2))):
        main.validate_python()
        assert mock_exit.called is True

    mock_exit.reset_mock()

    with patch("sys.version_info", new_callable=PropertyMock(return_value=(3, 5, 2))):
        main.validate_python()
        assert mock_exit.called is True

    mock_exit.reset_mock()

    with patch(
        "sys.version_info",
        new_callable=PropertyMock(
            return_value=(REQUIRED_PYTHON_VER[0] - 1,) + REQUIRED_PYTHON_VER[1:]
        ),
    ):
        main.validate_python()
        assert mock_exit.called is True

    mock_exit.reset_mock()

    with patch(
        "sys.version_info", new_callable=PropertyMock(return_value=REQUIRED_PYTHON_VER)
    ):
        main.validate_python()
        assert mock_exit.called is False

    mock_exit.reset_mock()

    with patch(
        "sys.version_info",
        new_callable=PropertyMock(
            return_value=(REQUIRED_PYTHON_VER[:2]) + (REQUIRED_PYTHON_VER[2] + 1,)
        ),
    ):
        main.validate_python()
        assert mock_exit.called is False

    mock_exit.reset_mock()
