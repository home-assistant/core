"""Test methods in __main__."""

from unittest.mock import PropertyMock, patch

from homeassistant import __main__ as main
from homeassistant.const import REQUIRED_PYTHON_VER


@patch("sys.exit")
def test_validate_python(mock_exit) -> None:
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


@patch("sys.exit")
def test_skip_pip_mutually_exclusive(mock_exit) -> None:
    """Test --skip-pip and --skip-pip-package are mutually exclusive."""

    def parse_args(*args):
        with patch("sys.argv", ["python", *args]):
            return main.get_arguments()

    args = parse_args("--skip-pip")
    assert args.skip_pip is True

    args = parse_args("--skip-pip-packages", "foo")
    assert args.skip_pip is False
    assert args.skip_pip_packages == ["foo"]

    args = parse_args("--skip-pip-packages", "foo-asd,bar-xyz")
    assert args.skip_pip is False
    assert args.skip_pip_packages == ["foo-asd", "bar-xyz"]

    assert mock_exit.called is False
    args = parse_args("--skip-pip", "--skip-pip-packages", "foo")
    assert mock_exit.called is True
