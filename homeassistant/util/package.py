"""Helpers to install PyPi packages."""
import os
import subprocess
import sys

from . import environment as env

# If we are not in a virtual environment, install in user space
INSTALL_USER = not env.is_virtual()


def install_package(package, upgrade=False, target=None):
    """Install a package on PyPi. Accepts pip compatible package strings.
    Return boolean if install successfull."""
    # Not using 'import pip; pip.main([])' because it breaks the logger
    args = [sys.executable, '-m', 'pip', 'install', '--quiet', package]
    if upgrade:
        args.append('--upgrade')
    if target:
        args += ['--target', os.path.abspath(target)]
    try:
        return 0 == subprocess.call(args)
    except subprocess.SubprocessError:
        return False
