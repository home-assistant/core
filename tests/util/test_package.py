"""Test Home Assistant package util methods."""

import asyncio
from importlib.metadata import metadata
import logging
import os
from subprocess import PIPE
import sys
from unittest.mock import MagicMock, call, patch

import pytest

from homeassistant.util import package

RESOURCE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "resources")
)

TEST_NEW_REQ = "pyhelloworld3==1.0.0"

TEST_ZIP_REQ = "file://{}#{}".format(
    os.path.join(RESOURCE_DIR, "pyhelloworld3.zip"), TEST_NEW_REQ
)


@pytest.fixture
def mock_sys():
    """Mock sys."""
    with patch("homeassistant.util.package.sys", spec=object) as sys_mock:
        sys_mock.executable = "python3"
        yield sys_mock


@pytest.fixture
def deps_dir():
    """Return path to deps directory."""
    return os.path.abspath("/deps_dir")


@pytest.fixture
def lib_dir(deps_dir):
    """Return path to lib directory."""
    return os.path.join(deps_dir, "lib_dir")


@pytest.fixture
def mock_popen(lib_dir):
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
def mock_env_copy():
    """Mock os.environ.copy."""
    with patch("homeassistant.util.package.os.environ.copy") as env_copy:
        env_copy.return_value = {}
        yield env_copy


@pytest.fixture
def mock_venv():
    """Mock homeassistant.util.package.is_virtual_env."""
    with patch("homeassistant.util.package.is_virtual_env") as mock:
        mock.return_value = True
        yield mock


def mock_async_subprocess():
    """Return an async Popen mock."""
    async_popen = MagicMock()

    async def communicate(input=None):
        """Communicate mock."""
        stdout = bytes("/deps_dir/lib_dir", "utf-8")
        return (stdout, None)

    async_popen.communicate = communicate
    return async_popen


def test_install(mock_sys, mock_popen, mock_env_copy, mock_venv) -> None:
    """Test an install attempt on a package that doesn't exist."""
    env = mock_env_copy()
    assert package.install_package(TEST_NEW_REQ, False)
    assert mock_popen.call_count == 2
    assert mock_popen.mock_calls[0] == call(
        [mock_sys.executable, "-m", "pip", "install", "--quiet", TEST_NEW_REQ],
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        env=env,
        close_fds=False,
    )
    assert mock_popen.return_value.communicate.call_count == 1


def test_install_upgrade(mock_sys, mock_popen, mock_env_copy, mock_venv) -> None:
    """Test an upgrade attempt on a package."""
    env = mock_env_copy()
    assert package.install_package(TEST_NEW_REQ)
    assert mock_popen.call_count == 2
    assert mock_popen.mock_calls[0] == call(
        [
            mock_sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            TEST_NEW_REQ,
            "--upgrade",
        ],
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        env=env,
        close_fds=False,
    )
    assert mock_popen.return_value.communicate.call_count == 1


def test_install_target(mock_sys, mock_popen, mock_env_copy, mock_venv) -> None:
    """Test an install with a target."""
    target = "target_folder"
    env = mock_env_copy()
    env["PYTHONUSERBASE"] = os.path.abspath(target)
    mock_venv.return_value = False
    mock_sys.platform = "linux"
    args = [
        mock_sys.executable,
        "-m",
        "pip",
        "install",
        "--quiet",
        TEST_NEW_REQ,
        "--user",
    ]

    assert package.install_package(TEST_NEW_REQ, False, target=target)
    assert mock_popen.call_count == 2
    assert mock_popen.mock_calls[0] == call(
        args, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=env, close_fds=False
    )
    assert mock_popen.return_value.communicate.call_count == 1


def test_install_target_venv(mock_sys, mock_popen, mock_env_copy, mock_venv) -> None:
    """Test an install with a target in a virtual environment."""
    target = "target_folder"
    with pytest.raises(AssertionError):
        package.install_package(TEST_NEW_REQ, False, target=target)


def test_install_error(
    caplog: pytest.LogCaptureFixture, mock_sys, mock_popen, mock_venv
) -> None:
    """Test an install that errors out."""
    caplog.set_level(logging.WARNING)
    mock_popen.return_value.returncode = 1
    assert not package.install_package(TEST_NEW_REQ)
    assert len(caplog.records) == 1
    for record in caplog.records:
        assert record.levelname == "ERROR"


def test_install_constraint(mock_sys, mock_popen, mock_env_copy, mock_venv) -> None:
    """Test install with constraint file on not installed package."""
    env = mock_env_copy()
    constraints = "constraints_file.txt"
    assert package.install_package(TEST_NEW_REQ, False, constraints=constraints)
    assert mock_popen.call_count == 2
    assert mock_popen.mock_calls[0] == call(
        [
            mock_sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            TEST_NEW_REQ,
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
