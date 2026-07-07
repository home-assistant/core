"""Test methods in __main__."""

from unittest.mock import Mock, call, patch

import pytest

from homeassistant import __main__ as main
from homeassistant.const import REQUIRED_PYTHON_VER, RESTART_EXIT_CODE

_PYTHON_VERSION_ERROR = (
    "Home Assistant requires at least Python "
    f"{REQUIRED_PYTHON_VER[0]}.{REQUIRED_PYTHON_VER[1]}.{REQUIRED_PYTHON_VER[2]}\n"
)


@patch("sys.exit")
@pytest.mark.parametrize(
    ("version_info", "expected_exit_calls", "expected_stderr"),
    [
        ((2, 7, 8), [call(1)], _PYTHON_VERSION_ERROR),
        ((3, 2, 0), [call(1)], _PYTHON_VERSION_ERROR),
        ((3, 4, 2), [call(1)], _PYTHON_VERSION_ERROR),
        ((3, 5, 2), [call(1)], _PYTHON_VERSION_ERROR),
        (
            # previous major version should fail
            (REQUIRED_PYTHON_VER[0] - 1, *REQUIRED_PYTHON_VER[1:]),
            [call(1)],
            _PYTHON_VERSION_ERROR,
        ),
        (REQUIRED_PYTHON_VER, [], ""),
        (
            # next patch version should pass
            (*REQUIRED_PYTHON_VER[:2], REQUIRED_PYTHON_VER[2] + 1),
            [],
            "",
        ),
    ],
)
def test_validate_python(
    mock_exit: Mock,
    version_info: tuple[int, int, int],
    expected_exit_calls: list[call],
    expected_stderr: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test validate Python version method."""
    with patch("sys.version_info", new=version_info):
        main.validate_python()
    assert mock_exit.call_args_list == expected_exit_calls
    assert capsys.readouterr().err == expected_stderr


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
