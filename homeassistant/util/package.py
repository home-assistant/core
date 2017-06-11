"""Helpers to install PyPi packages."""
import logging
import os
import sys
import threading
from subprocess import Popen, PIPE
from urllib.parse import urlparse

from typing import Optional

import pkg_resources

_LOGGER = logging.getLogger(__name__)

INSTALL_LOCK = threading.Lock()


def install_package(package: str, upgrade: bool=True,
                    target: Optional[str]=None,
                    constraints: Optional[str]=None) -> bool:
    """Install a package on PyPi. Accepts pip compatible package strings.

    Return boolean if install successful.
    """
    # Not using 'import pip; pip.main([])' because it breaks the logger
    with INSTALL_LOCK:
        if check_package_exists(package, target):
            return True

        _LOGGER.info("Attempting install of %s", package)
        args = [sys.executable, '-m', 'pip', 'install', '--quiet', package]
        if upgrade:
            args.append('--upgrade')
        if target:
            args += ['--target', os.path.abspath(target)]

        if constraints is not None:
            args += ['--constraint', constraints]

        process = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        _, stderr = process.communicate()
        if process.returncode != 0:
            _LOGGER.error("Unable to install package %s: %s",
                          package, stderr.decode('utf-8').lstrip().strip())
            return False

        return True


def check_package_exists(package: str, lib_dir: str) -> bool:
    """Check if a package is installed globally or in lib_dir.

    Returns True when the requirement is met.
    Returns False when the package is not installed or doesn't meet req.
    """
    try:
        req = pkg_resources.Requirement.parse(package)
    except ValueError:
        # This is a zip file
        req = pkg_resources.Requirement.parse(urlparse(package).fragment)

    # Check packages from lib dir
    if lib_dir is not None:
        if any(dist in req for dist in
               pkg_resources.find_distributions(lib_dir)):
            return True

    # Check packages from global + virtual environment
    # pylint: disable=not-an-iterable
    return any(dist in req for dist in pkg_resources.working_set)
