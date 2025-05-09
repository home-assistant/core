"""Helpers to install PyPi packages."""

from __future__ import annotations

import asyncio
from functools import cache
from importlib.metadata import PackageNotFoundError, version
import logging
import os
from pathlib import Path
import site
from subprocess import PIPE, Popen
import sys
from urllib.parse import urlparse

from packaging.requirements import InvalidRequirement, Requirement

from .system_info import is_official_image

_LOGGER = logging.getLogger(__name__)


def is_virtual_env() -> bool:
    """Return if we run in a virtual environment."""
    # Check supports venv && virtualenv
    return getattr(sys, "base_prefix", sys.prefix) != sys.prefix or hasattr(
        sys, "real_prefix"
    )

@cache
def is_docker_env() -> bool:
    """Return True if we run in a container env, unless CONTAINER_NON_PRIVILEGED=True."""
    if os.environ.get("CONTAINER_NON_PRIVILEGED") == "True":
        return False

    return (
        Path("/.dockerenv").exists()
        or Path("/run/.containerenv").exists()
        or "KUBERNETES_SERVICE_HOST" in os.environ
        or is_official_image()
    )

def get_installed_versions(specifiers: set[str]) -> set[str]:
    """Return a set of installed packages and versions."""
    return {specifier for specifier in specifiers if is_installed(specifier)}


def is_installed(requirement_str: str) -> bool:
    """Check if a package is installed and will be loaded when we import it.

    expected input is a pip compatible package specifier (requirement string)
    e.g. "package==1.0.0" or "package>=1.0.0,<2.0.0"

    For backward compatibility, it also accepts a URL with a fragment
    e.g. "git+https://github.com/pypa/pip#pip>=1"

    Returns True when the requirement is met.
    Returns False when the package is not installed or doesn't meet req.
    """
    try:
        req = Requirement(requirement_str)
    except InvalidRequirement:
        if "#" not in requirement_str:
            _LOGGER.error("Invalid requirement '%s'", requirement_str)
            return False

        # This is likely a URL with a fragment
        # example: git+https://github.com/pypa/pip#pip>=1

        # fragment support was originally used to install zip files, and
        # we no longer do this in Home Assistant. However, custom
        # components started using it to install packages from git
        # urls which would make it would be a breaking change to
        # remove it.
        try:
            req = Requirement(urlparse(requirement_str).fragment)
        except InvalidRequirement:
            _LOGGER.error("Invalid requirement '%s'", requirement_str)
            return False

    try:
        if (installed_version := version(req.name)) is None:
            # This can happen when an install failed or
            # was aborted while in progress see
            # https://github.com/home-assistant/core/issues/47699
            _LOGGER.error(  # type: ignore[unreachable]
                "Installed version for %s resolved to None", req.name
            )
            return False
        return req.specifier.contains(installed_version, prereleases=True)
    except PackageNotFoundError:
        return False


_UV_ENV_PYTHON_VARS = (
    "UV_SYSTEM_PYTHON",
    "UV_PYTHON",
)


def install_package(
    package: str,
    upgrade: bool = True,
    target: str | None = None,
    constraints: str | None = None,
    timeout: int | None = None,
) -> bool:
    """Install a package on PyPi. Accepts pip compatible package strings.

    Return boolean if install successful.
    """
    _LOGGER.info("Attempting install of %s", package)
    env = os.environ.copy()
    args = [
        sys.executable,
        "-m",
        "uv",
        "pip",
        "install",
        "--quiet",
        package,
        # We need to use unsafe-first-match for custom components
        # which can use a different version of a package than the one
        # we have built the wheel for.
        "--index-strategy",
        "unsafe-first-match",
    ]
    if timeout:
        env["HTTP_TIMEOUT"] = str(timeout)
    if upgrade:
        args.append("--upgrade")
    if constraints is not None:
        args += ["--constraint", constraints]
    if target:
        abs_target = os.path.abspath(target)
        args += ["--target", abs_target]
    elif (
        not is_virtual_env()
        and not (any(var in env for var in _UV_ENV_PYTHON_VARS))
        and (abs_target := site.getusersitepackages())
    ):
        # Pip compatibility
        # Uv has currently no support for --user
        # See https://github.com/astral-sh/uv/issues/2077
        # Using workaround to install to site-packages
        # https://github.com/astral-sh/uv/issues/2077#issuecomment-2150406001
        args += ["--python", sys.executable, "--target", abs_target]

    _LOGGER.debug("Running uv pip command: args=%s", args)
    with Popen(
        args,
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        env=env,
        close_fds=False,  # required for posix_spawn
    ) as process:
        _, stderr = process.communicate()
        if process.returncode != 0:
            _LOGGER.error(
                "Unable to install package %s: %s",
                package,
                stderr.decode("utf-8").lstrip().strip(),
            )
            return False

    return True


async def async_get_user_site(deps_dir: str) -> str:
    """Return user local library path.

    This function is a coroutine.
    """
    env = os.environ.copy()
    env["PYTHONUSERBASE"] = os.path.abspath(deps_dir)
    args = [sys.executable, "-m", "site", "--user-site"]
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=env,
        close_fds=False,  # required for posix_spawn
    )
    stdout, _ = await process.communicate()
    return stdout.decode().strip()
