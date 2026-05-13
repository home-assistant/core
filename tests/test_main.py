"""Test methods in __main__."""

from unittest.mock import Mock, PropertyMock, call, patch

import pytest

from homeassistant import __main__ as main
from homeassistant.const import REQUIRED_PYTHON_VER, RESTART_EXIT_CODE


@patch("sys.exit")
@pytest.mark.parametrize(
    ("is_venv", "is_docker", "expected_exit_calls", "expected_stderr"),
    [
        (
            False,
            False,
            [call(1)],
            "Home Assistant must be run in a Python virtual environment or a container.\n",
        ),
        (True, False, [], ""),
        (False, True, [], ""),
        (True, True, [], ""),
    ],
)
def test_validate_environment(
    mock_exit: Mock,
    is_venv: bool,
    is_docker: bool,
    expected_exit_calls: list[call],
    expected_stderr: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test validate Python environment."""
    with (
        patch("homeassistant.__main__.is_virtual_env", return_value=is_venv),
        patch("homeassistant.__main__.is_docker_env", return_value=is_docker),
    ):
        main.validate_environment()
    assert mock_exit.call_args_list == expected_exit_calls
    assert capsys.readouterr().err == expected_stderr


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
            return_value=(REQUIRED_PYTHON_VER[0] - 1, *REQUIRED_PYTHON_VER[1:])
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
            return_value=(*REQUIRED_PYTHON_VER[:2], REQUIRED_PYTHON_VER[2] + 1)
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


def test_restart_after_backup_restore() -> None:
    """Test restarting if we restored a backup."""
    with (
        patch("sys.argv", ["python"]),
        patch("homeassistant.__main__.restore_backup", return_value=True),
    ):
        exit_code = main.main()
        assert exit_code == RESTART_EXIT_CODE
