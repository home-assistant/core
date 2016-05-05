"""Helpers to install PyPi packages."""
import logging
import os
import subprocess
import sys
import threading
from urllib.parse import urlparse

import pkg_resources

_LOGGER = logging.getLogger(__name__)
INSTALL_LOCK = threading.Lock()


def install_package(package, upgrade=True, target=None):
    """Install a package on PyPi. Accepts pip compatible package strings.

    Return boolean if install successful.
    """
    # Not using 'import pip; pip.main([])' because it breaks the logger
    with INSTALL_LOCK:
        if check_package_exists(package, target):
            return True

        _LOGGER.info('Attempting install of %s', package)
        args = [sys.executable, '-m', 'pip', 'install', '--quiet', package]
        if upgrade:
            args.append('--upgrade')
        if target:
            args += ['--target', os.path.abspath(target)]

        try:
            return subprocess.call(args) == 0
        except subprocess.SubprocessError:
            _LOGGER.exception('Unable to install pacakge %s', package)
            return False


def check_package_exists(package, lib_dir):
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
