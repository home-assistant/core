"""Helpers to install PyPi packages."""
import asyncio
import logging
import os
from subprocess import PIPE, Popen
import sys
from typing import Optional

_LOGGER = logging.getLogger(__name__)


def is_virtual_env() -> bool:
    """Return if we run in a virtual environtment."""
    # Check supports venv && virtualenv
    return (getattr(sys, 'base_prefix', sys.prefix) != sys.prefix or
            hasattr(sys, 'real_prefix'))


def install_package(package: str, upgrade: bool = True,
                    target: Optional[str] = None,
                    constraints: Optional[str] = None) -> bool:
    """Install a package on PyPi. Accepts pip compatible package strings.

    Return boolean if install successful.
    """
    # Not using 'import pip; pip.main([])' because it breaks the logger
    _LOGGER.info('Attempting install of %s', package)
    env = os.environ.copy()
    args = [sys.executable, '-m', 'pip', 'install', '--quiet', package]
    if upgrade:
        args.append('--upgrade')
    if constraints is not None:
        args += ['--constraint', constraints]
    if target:
        assert not is_virtual_env()
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


async def async_get_user_site(deps_dir: str) -> str:
    """Return user local library path.

    This function is a coroutine.
    """
    env = os.environ.copy()
    env['PYTHONUSERBASE'] = os.path.abspath(deps_dir)
    args = [sys.executable, '-m', 'site', '--user-site']
    process = await asyncio.create_subprocess_exec(
        *args, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        env=env)
    stdout, _ = await process.communicate()
    lib_dir = stdout.decode().strip()
    return lib_dir
