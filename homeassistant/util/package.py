"""Helpers to install PyPi packages."""
import asyncio
import logging
import os
from subprocess import PIPE, Popen
import sys
import threading
from urllib.parse import urlparse

from pip.locations import running_under_virtualenv
from typing import Optional

import pkg_resources

_LOGGER = logging.getLogger(__name__)

INSTALL_LOCK = threading.Lock()


def install_package(package: str, upgrade: bool = True,
                    target: Optional[str] = None,
                    constraints: Optional[str] = None) -> bool:
    """Install a package on PyPi. Accepts pip compatible package strings.

    Return boolean if install successful.
    """
    # Not using 'import pip; pip.main([])' because it breaks the logger
    with INSTALL_LOCK:
        if check_package_exists(package):
            return True

        _LOGGER.info('Attempting install of %s', package)
        env = os.environ.copy()
        args = [sys.executable, '-m', 'pip', 'install', '--quiet', package]
        if upgrade:
            args.append('--upgrade')
        if constraints is not None:
            args += ['--constraint', constraints]
        if target:
            assert not running_under_virtualenv()
            # This only works if not running in venv
            args += ['--user']
            env['PYTHONUSERBASE'] = os.path.abspath(target)
            if sys.platform != 'win32':
                # Workaround for incompatible prefix setting
                # See http://stackoverflow.com/a/4495175
                args += ['--prefix=']
        process = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=env)
        _, stderr = process.communicate()
        if process.returncode != 0:
            _LOGGER.error("Unable to install package %s: %s",
                          package, stderr.decode('utf-8').lstrip().strip())
            return False

        return True


def check_package_exists(package: str) -> bool:
    """Check if a package is installed globally or in lib_dir.

    Returns True when the requirement is met.
    Returns False when the package is not installed or doesn't meet req.
    """
    try:
        req = pkg_resources.Requirement.parse(package)
    except ValueError:
        # This is a zip file
        req = pkg_resources.Requirement.parse(urlparse(package).fragment)

    env = pkg_resources.Environment()
    return any(dist in req for dist in env[req.project_name])


def _get_user_site(deps_dir: str) -> tuple:
    """Get arguments and environment for subprocess used in get_user_site."""
    env = os.environ.copy()
    env['PYTHONUSERBASE'] = os.path.abspath(deps_dir)
    args = [sys.executable, '-m', 'site', '--user-site']
    return args, env


def get_user_site(deps_dir: str) -> str:
    """Return user local library path."""
    args, env = _get_user_site(deps_dir)
    process = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, env=env)
    stdout, _ = process.communicate()
    lib_dir = stdout.decode().strip()
    return lib_dir


@asyncio.coroutine
def async_get_user_site(deps_dir: str, loop: asyncio.AbstractEventLoop) -> str:
    """Return user local library path.

    This function is a coroutine.
    """
    args, env = _get_user_site(deps_dir)
    process = yield from asyncio.create_subprocess_exec(
        *args, loop=loop, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        env=env)
    stdout, _ = yield from process.communicate()
    lib_dir = stdout.decode().strip()
    return lib_dir
