"""Helpers to install PyPi packages."""
from __future__ import annotations

import asyncio
from importlib.metadata import PackageNotFoundError, version
import logging
import os
from pathlib import Path
from subprocess import PIPE, Popen
import sys
from urllib.parse import urlparse

import pkg_resources

_LOGGER = logging.getLogger(__name__)


def is_virtual_env() -> bool:
    """Return if we run in a virtual environment."""
    # Check supports venv && virtualenv
    return getattr(sys, "base_prefix", sys.prefix) != sys.prefix or hasattr(
        sys, "real_prefix"
    )


def is_docker_env() -> bool:
    """Return True if we run in a docker env."""
    return Path("/.dockerenv").exists()


def is_installed(package: str) -> bool:
    """Check if a package is installed and will be loaded when we import it.

    Returns True when the requirement is met.
    Returns False when the package is not installed or doesn't meet req.
    """
    try:
        pkg_resources.get_distribution(package)
        return True
    except (pkg_resources.ResolutionError, pkg_resources.ExtractionError):
        req = pkg_resources.Requirement.parse(package)
    except ValueError:
        # This is a zip file. We no longer use this in Home Assistant,
        # leaving it in for custom components.
        req = pkg_resources.Requirement.parse(urlparse(package).fragment)

    try:
        installed_version = version(req.project_name)
        # This will happen when an install failed or
        # was aborted while in progress see
        # https://github.com/home-assistant/core/issues/47699
        if installed_version is None:
            _LOGGER.error("Installed version for %s resolved to None", req.project_name)  # type: ignore
            return False
        return installed_version in req
    except PackageNotFoundError:
        return False


def install_package(
    package: str,
    upgrade: bool = True,
    target: str | None = None,
    constraints: str | None = None,
    find_links: str | None = None,
    timeout: int | None = None,
    no_cache_dir: bool | None = False,
) -> bool:
    """Install a package on PyPi. Accepts pip compatible package strings.

    Return boolean if install successful.
    """
    # Not using 'import pip; pip.main([])' because it breaks the logger
    _LOGGER.info("Attempting install of %s", package)
    from homeassistant.components.ais_dom import ais_global

    package_name = str(package).split("==")[0]
    package_name = package_name.split(">=")[0]
    ais_global.say_direct(
        "Instaluje zależności pakietu: " + package_name + "; poczekaj."
    )
    env = os.environ.copy()
    # AIS dom prefer to use the version of libsodium provided by distribution
    # SODIUM_INSTALL=system pip install pynacl
    if package.lower().startswith("pynacl"):
        # "SODIUM_INSTALL=system pip install --quiet " + package
        env["SODIUM_INSTALL"] = "system"
    if package.lower().startswith("pillow"):
        # LDFLAGS="-L/system/lib/" CFLAGS="-I/data/data/pl.sviete.dom/files/usr/include/" pip install Pillow
        env["LDFLAGS"] = "-L/system/lib/"
        env["CFLAGS"] = "-I/data/data/pl.sviete.dom/files/usr/include/"
    args = [sys.executable, "-m", "pip", "install", "--quiet", package]
    if timeout:
        args += ["--timeout", str(timeout)]
    if no_cache_dir:
        args.append("--no-cache-dir")
    if upgrade:
        args.append("--upgrade")
    if constraints is not None:
        args += ["--constraint", constraints]
    if find_links is not None:
        args += ["--find-links", find_links, "--prefer-binary"]

    # AIS dom don't install in deps dir <config>/deps
    # if target:
    #     assert not is_virtual_env()
    #     # This only works if not running in venv
    #     args += ["--user"]
    #     env["PYTHONUSERBASE"] = os.path.abspath(target)
    #     if sys.platform != "win32":
    #         # Workaround for incompatible prefix setting
    #         # See http://stackoverflow.com/a/4495175
    #         args += ["--prefix="]
    with Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=env) as process:
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
    )
    stdout, _ = await process.communicate()
    lib_dir = stdout.decode().strip()
    return lib_dir
