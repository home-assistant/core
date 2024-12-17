"""Test Home Assistant package util methods."""

import asyncio
from collections.abc import Generator
from importlib.metadata import metadata
import logging
import os
from subprocess import PIPE
import sys
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from homeassistant.util import package

RESOURCE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "resources")
)

TEST_NEW_REQ = "pyhelloworld3==1.0.0"

TEST_ZIP_REQ = f"file://{RESOURCE_DIR}/pyhelloworld3.zip#{TEST_NEW_REQ}"


@pytest.fixture
def mock_sys() -> Generator[MagicMock]:
    """Mock sys."""
    with patch("homeassistant.util.package.sys", spec=object) as sys_mock:
        sys_mock.executable = "python3"
        yield sys_mock


@pytest.fixture
def deps_dir() -> str:
    """Return path to deps directory."""
    return os.path.abspath("/deps_dir")


@pytest.fixture
def lib_dir(deps_dir) -> str:
    """Return path to lib directory."""
    return os.path.join(deps_dir, "lib_dir")


@pytest.fixture
def mock_popen(lib_dir) -> Generator[MagicMock]:
    """Return a Popen mock."""
    with patch("homeassistant.util.package.Popen") as popen_mock:
        popen_mock.return_value.__enter__ = popen_mock
        popen_mock.return_value.communicate.return_value = (
            bytes(lib_dir, "utf-8"),
            b"error",
        )
        popen_mock.return_value.returncode = 0
        yield popen_mock


@pytest.fixture
def mock_env_copy() -> Generator[Mock]:
    """Mock os.environ.copy."""
    with patch("homeassistant.util.package.os.environ.copy") as env_copy:
        env_copy.return_value = {}
        yield env_copy


@pytest.fixture
def mock_venv() -> Generator[MagicMock]:
    """Mock homeassistant.util.package.is_virtual_env."""
    with patch("homeassistant.util.package.is_virtual_env") as mock:
        mock.return_value = True
        yield mock


def mock_async_subprocess() -> Generator[MagicMock]:
    """Return an async Popen mock."""
    async_popen = MagicMock()

    async def communicate(input=None):
        """Communicate mock."""
        stdout = bytes("/deps_dir/lib_dir", "utf-8")
        return (stdout, None)

    async_popen.communicate = communicate
    return async_popen


@pytest.mark.usefixtures("mock_venv")
def test_install(
    mock_popen: MagicMock, mock_env_copy: MagicMock, mock_sys: MagicMock
) -> None:
    """Test an install attempt on a package that doesn't exist."""
    env = mock_env_copy()
    assert package.install_package(TEST_NEW_REQ, False)
    assert mock_popen.call_count == 2
    assert mock_popen.mock_calls[0] == call(
        [
            mock_sys.executable,
            "-m",
            "uv",
            "pip",
            "install",
            "--quiet",
            TEST_NEW_REQ,
            "--index-strategy",
            "unsafe-first-match",
        ],
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        env=env,
        close_fds=False,
    )
    assert mock_popen.return_value.communicate.call_count == 1


@pytest.mark.usefixtures("mock_venv")
def test_install_with_timeout(
    mock_popen: MagicMock, mock_env_copy: MagicMock, mock_sys: MagicMock
) -> None:
    """Test an install attempt on a package that doesn't exist with a timeout set."""
    env = mock_env_copy()
    assert package.install_package(TEST_NEW_REQ, False, timeout=10)
    assert mock_popen.call_count == 2
    env["HTTP_TIMEOUT"] = "10"
    assert mock_popen.mock_calls[0] == call(
        [
            mock_sys.executable,
            "-m",
            "uv",
            "pip",
            "install",
            "--quiet",
            TEST_NEW_REQ,
            "--index-strategy",
            "unsafe-first-match",
        ],
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        env=env,
        close_fds=False,
    )
    assert mock_popen.return_value.communicate.call_count == 1


@pytest.mark.usefixtures("mock_venv")
def test_install_upgrade(mock_popen, mock_env_copy, mock_sys) -> None:
    """Test an upgrade attempt on a package."""
    env = mock_env_copy()
    assert package.install_package(TEST_NEW_REQ)
    assert mock_popen.call_count == 2
    assert mock_popen.mock_calls[0] == call(
        [
            mock_sys.executable,
            "-m",
            "uv",
            "pip",
            "install",
            "--quiet",
            TEST_NEW_REQ,
            "--index-strategy",
            "unsafe-first-match",
            "--upgrade",
        ],
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        env=env,
        close_fds=False,
    )
    assert mock_popen.return_value.communicate.call_count == 1


@pytest.mark.parametrize(
    "is_venv",
    [
        True,
        False,
    ],
)
def test_install_target(
    mock_sys: MagicMock,
    mock_popen: MagicMock,
    mock_env_copy: MagicMock,
    mock_venv: MagicMock,
    is_venv: bool,
) -> None:
    """Test an install with a target."""
    target = "target_folder"
    env = mock_env_copy()
    abs_target = os.path.abspath(target)
    env["PYTHONUSERBASE"] = abs_target
    mock_venv.return_value = is_venv
    mock_sys.platform = "linux"
    args = [
        mock_sys.executable,
        "-m",
        "uv",
        "pip",
        "install",
        "--quiet",
        TEST_NEW_REQ,
        "--index-strategy",
        "unsafe-first-match",
        "--target",
        abs_target,
    ]

    assert package.install_package(TEST_NEW_REQ, False, target=target)
    assert mock_popen.call_count == 2
    assert mock_popen.mock_calls[0] == call(
        args, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=env, close_fds=False
    )
    assert mock_popen.return_value.communicate.call_count == 1


@pytest.mark.parametrize(
    ("in_venv", "additional_env_vars"),
    [
        (True, {}),
        (False, {"UV_SYSTEM_PYTHON": "true"}),
        (False, {"UV_PYTHON": "python3"}),
        (False, {"UV_SYSTEM_PYTHON": "true", "UV_PYTHON": "python3"}),
    ],
    ids=["in_venv", "UV_SYSTEM_PYTHON", "UV_PYTHON", "UV_SYSTEM_PYTHON and UV_PYTHON"],
)
def test_install_pip_compatibility_no_workaround(
    mock_sys: MagicMock,
    mock_popen: MagicMock,
    mock_env_copy: MagicMock,
    mock_venv: MagicMock,
    in_venv: bool,
    additional_env_vars: dict[str, str],
) -> None:
    """Test install will not use pip fallback."""
    env = mock_env_copy()
    env.update(additional_env_vars)
    mock_venv.return_value = in_venv
    mock_sys.platform = "linux"
    args = [
        mock_sys.executable,
        "-m",
        "uv",
        "pip",
        "install",
        "--quiet",
        TEST_NEW_REQ,
        "--index-strategy",
        "unsafe-first-match",
    ]

    assert package.install_package(TEST_NEW_REQ, False)
    assert mock_popen.call_count == 2
    assert mock_popen.mock_calls[0] == call(
        args, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=env, close_fds=False
    )
    assert mock_popen.return_value.communicate.call_count == 1


def test_install_pip_compatibility_use_workaround(
    mock_sys: MagicMock,
    mock_popen: MagicMock,
    mock_env_copy: MagicMock,
    mock_venv: MagicMock,
) -> None:
    """Test install will use pip compatibility fallback."""
    env = mock_env_copy()
    mock_venv.return_value = False
    mock_sys.platform = "linux"
    python = "python3"
    mock_sys.executable = python
    site_dir = "/site_dir"
    args = [
        mock_sys.executable,
        "-m",
        "uv",
        "pip",
        "install",
        "--quiet",
        TEST_NEW_REQ,
        "--index-strategy",
        "unsafe-first-match",
        "--python",
        python,
        "--target",
        site_dir,
    ]

    with patch("homeassistant.util.package.site", autospec=True) as site_mock:
        site_mock.getusersitepackages.return_value = site_dir
        assert package.install_package(TEST_NEW_REQ, False)

    assert mock_popen.call_count == 2
    assert mock_popen.mock_calls[0] == call(
        args, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=env, close_fds=False
    )
    assert mock_popen.return_value.communicate.call_count == 1


@pytest.mark.usefixtures("mock_sys", "mock_venv")
def test_install_error(caplog: pytest.LogCaptureFixture, mock_popen) -> None:
    """Test an install that errors out."""
    caplog.set_level(logging.WARNING)
    mock_popen.return_value.returncode = 1
    assert not package.install_package(TEST_NEW_REQ)
    assert len(caplog.records) == 1
    for record in caplog.records:
        assert record.levelname == "ERROR"


@pytest.mark.usefixtures("mock_venv")
def test_install_constraint(mock_popen, mock_env_copy, mock_sys) -> None:
    """Test install with constraint file on not installed package."""
    env = mock_env_copy()
    constraints = "constraints_file.txt"
    assert package.install_package(TEST_NEW_REQ, False, constraints=constraints)
    assert mock_popen.call_count == 2
    assert mock_popen.mock_calls[0] == call(
        [
            mock_sys.executable,
            "-m",
            "uv",
            "pip",
            "install",
            "--quiet",
            TEST_NEW_REQ,
            "--index-strategy",
            "unsafe-first-match",
            "--constraint",
            constraints,
        ],
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        env=env,
        close_fds=False,
    )
    assert mock_popen.return_value.communicate.call_count == 1


async def test_async_get_user_site(mock_env_copy) -> None:
    """Test async get user site directory."""
    deps_dir = "/deps_dir"
    env = mock_env_copy()
    env["PYTHONUSERBASE"] = os.path.abspath(deps_dir)
    args = [sys.executable, "-m", "site", "--user-site"]
    with patch(
        "homeassistant.util.package.asyncio.create_subprocess_exec",
        return_value=mock_async_subprocess(),
    ) as popen_mock:
        ret = await package.async_get_user_site(deps_dir)
    assert popen_mock.call_count == 1
    assert popen_mock.call_args == call(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=env,
        close_fds=False,
    )
    assert ret == os.path.join(deps_dir, "lib_dir")


def test_check_package_global(caplog: pytest.LogCaptureFixture) -> None:
    """Test for an installed package."""
    pkg = metadata("homeassistant")
    installed_package = pkg["name"]
    installed_version = pkg["version"]

    assert package.is_installed(installed_package)
    assert package.is_installed(f"{installed_package}=={installed_version}")
    assert package.is_installed(f"{installed_package}>={installed_version}")
    assert package.is_installed(f"{installed_package}<={installed_version}")
    assert not package.is_installed(f"{installed_package}<{installed_version}")

    assert package.is_installed("-1 invalid_package") is False
    assert "Invalid requirement '-1 invalid_package'" in caplog.text


def test_check_package_fragment(caplog: pytest.LogCaptureFixture) -> None:
    """Test for an installed package with a fragment."""
    assert not package.is_installed(TEST_ZIP_REQ)
    assert package.is_installed("git+https://github.com/pypa/pip#pip>=1")
    assert not package.is_installed("git+https://github.com/pypa/pip#-1 invalid")
    assert (
        "Invalid requirement 'git+https://github.com/pypa/pip#-1 invalid'"
        in caplog.text
    )


def test_get_is_installed() -> None:
    """Test is_installed can parse complex requirements."""
    pkg = metadata("homeassistant")
    installed_package = pkg["name"]
    installed_version = pkg["version"]

    assert package.is_installed(installed_package)
    assert package.is_installed(f"{installed_package}=={installed_version}")
    assert package.is_installed(f"{installed_package}>={installed_version}")
    assert package.is_installed(f"{installed_package}<={installed_version}")
    assert not package.is_installed(f"{installed_package}<{installed_version}")


def test_check_package_previous_failed_install() -> None:
    """Test for when a previously install package failed and left cruft behind."""
    pkg = metadata("homeassistant")
    installed_package = pkg["name"]
    installed_version = pkg["version"]

    with patch("homeassistant.util.package.version", return_value=None):
        assert not package.is_installed(installed_package)
        assert not package.is_installed(f"{installed_package}=={installed_version}")
