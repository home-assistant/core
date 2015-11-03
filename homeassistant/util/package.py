"""Helpers to install PyPi packages."""
import logging
import os
import pkg_resources
import subprocess
import sys
import threading
from urllib.parse import urlparse

_LOGGER = logging.getLogger(__name__)
INSTALL_LOCK = threading.Lock()


def install_package(package, upgrade=True, target=None):
    """Install a package on PyPi. Accepts pip compatible package strings.
    Return boolean if install successfull."""
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
            return 0 == subprocess.call(args)
        except subprocess.SubprocessError:
            return False


def check_package_exists(package, target):
    """Check if a package exists.
    Returns True when the requirement is met.
    Returns False when the package is not installed or doesn't meet req."""
    try:
        req = pkg_resources.Requirement.parse(package)
    except ValueError:
        # This is a zip file
        req = pkg_resources.Requirement.parse(urlparse(package).fragment)

    return any(dist in req for dist in
               pkg_resources.find_distributions(target))
